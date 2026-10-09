"""Isolated test clients and server for the Sections tests.

Everything a run uses comes from a parallel test slot of the workspace
(se/notes/parallel-test-work/NOTE.md), so several sessions can test at once:

    SECTIONS_SLOT=11 python -m pytest tests

Client i of slot n gets its own Pulsar folder ~/.se-test/<task>-c<i>, game user
data folder ~/.se-test/<task>-c<i>-data, Remote port 25000 + 10n + i and client
id 76561199500010000 + 10n + i, where <task> is the slot's owner. Server i gets
~/.se-test/<task>-ds<i> and UDP port 28000 + 10n + i. Without SECTIONS_SLOT the
rig falls back to the single fixed client the older checks were written for:
~/.se-test/sections, port 24188.

Every launch goes through run-test.sh, which waits for 8 GiB of free RAM after
the launch and for a running benchmark to finish. The Pulsar folders compile
Remote and Sections from the working copies as dev folders.

From the command line, to run the older script checks by hand:

    SECTIONS_SLOT=11 python tests/rig.py start [--render] [--earth] [Key=Value ...]
    SECTIONS_SLOT=11 python tests/rig.py stop
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

HOME = Path.home()
REPO = Path(__file__).resolve().parent.parent
PLUGINS = REPO.parent
REMOTE_REPO = PLUGINS / "remote"
WORKSPACE = REPO.parents[2]
PARALLEL = WORKSPACE / "notes" / "parallel-test-work"

sys.path.insert(0, str(REMOTE_REPO / "skills" / "se-remote"))
from se_remote import RemoteAPI  # noqa: E402

SECTIONS_ID = "viktor-ferenczi/se-sections"
PULSAR_TEMPLATE = Path(
    os.environ.get("SECTIONS_PULSAR_TEMPLATE", HOME / ".config/Pulsar")
)
# The Remote suite's worlds. The fixture tests use the space world; the older
# scripts expect the upright character of the Earth world.
WORLDS = REMOTE_REPO / "Worlds"
SPACE, EARTH = "RemoteAPITestSpace", "RemoteAPITestEarthPlanet"
WORLD_NAME = "SectionsTest"
LAUNCHER = "SectionsInterim.bin"

# RSS of one client, settled in a world, for the RAM guard (NOTE.md, section 3)
NEED_GIB = {"render": 5.5, "no-render": 3.7}
SERVER_NEED_GIB = 4.0

# Settings for unattended runs. The rest keep the plugin's defaults.
SECTIONS_CONFIG = {
    "CutConfirmation": "false",
    "DeleteConfirmation": "false",
    # Automatic numbering instead of the name dialog
    "RenameBlueprint": "false",
    "IncludeIntersectingBlocks": "false",
    "HiddenBlockOpacity": "10",
    "HiddenBlockSaturation": "100",
}


def _slot() -> tuple[int, str] | None:
    value = os.environ.get("SECTIONS_SLOT")
    if not value:
        return None
    owner = (
        Path(os.environ.get("SE_TEST_SLOTS", HOME / ".se-test/slots")) / value / "owner"
    )
    if not owner.exists():
        raise RuntimeError(f"Slot {value} is not claimed, see {PARALLEL / 'NOTE.md'}")
    return int(value), owner.read_text().strip()


SLOT = _slot()


@dataclass
class Client:
    pulsar: Path
    appdata: Path
    port: int
    client_id: int | None

    @property
    def launcher(self) -> Path:
        return self.pulsar / LAUNCHER

    @property
    def pid_file(self) -> Path:
        return self.appdata / "game.pid"

    @property
    def log(self) -> Path:
        return self.appdata / "SpaceEngineers.log"

    @property
    def world(self) -> Path:
        return self.appdata / "Saves" / "tests" / WORLD_NAME

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


@dataclass
class Server:
    root: Path
    port: int
    steam_port: int

    @property
    def config(self) -> Path:
        return self.root / "magnetar"

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def world(self) -> Path:
        return self.data / "Saves" / WORLD_NAME

    @property
    def log(self) -> Path:
        return self.root / "server.log"

    @property
    def pid_file(self) -> Path:
        return self.root / "server.pid"


def client(i: int = 0) -> Client:
    if SLOT is None:
        if i:
            raise RuntimeError("More than one client needs SECTIONS_SLOT")
        return Client(
            HOME / ".se-test/sections", HOME / ".se-test/sections-data", 24188, None
        )
    n, task = SLOT
    return Client(
        HOME / f".se-test/{task}-c{i}",
        HOME / f".se-test/{task}-c{i}-data",
        25000 + 10 * n + i,
        76561199500010000 + 10 * n + i,
    )


def server(i: int = 0) -> Server:
    if SLOT is None:
        raise RuntimeError("The dedicated server tests need SECTIONS_SLOT")
    n, task = SLOT
    return Server(
        HOME / f".se-test/{task}-ds{i}", 28000 + 10 * n + i, 29000 + 10 * n + i
    )


def remote_url() -> str:
    """The Remote API of client 0; SE_REMOTE_URL wins, for a client started by hand"""
    return os.environ.get("SE_REMOTE_URL") or client(0).url


def connect(c: Client | None = None) -> RemoteAPI:
    return RemoteAPI((c or client(0)).url, username="admin", password="SpaceEngineers")


# ---------------------------------------------------------------------------
# Pulsar folder and configuration
# ---------------------------------------------------------------------------


def _register_source(sources: Path, name: str, folder: Path, file: str) -> None:
    tree = ET.parse(sources)
    local = tree.getroot().find("LocalPluginSources")
    if local is None:
        local = ET.SubElement(tree.getroot(), "LocalPluginSources")
    for plugin in local.findall("LocalPlugin"):
        if plugin.findtext("Name") == name:
            local.remove(plugin)
    plugin = ET.SubElement(local, "LocalPlugin")
    for tag, value in (
        ("Name", name),
        ("Folder", str(folder)),
        ("File", file),
        ("Enabled", "true"),
    ):
        ET.SubElement(plugin, tag).text = value
    tree.write(sources, encoding="utf-8", xml_declaration=True)


def _profile(ids) -> str:
    folders = "".join(
        f"<LocalFolderConfig><Id>{i}</Id><DebugBuild>true</DebugBuild></LocalFolderConfig>"
        for i in ids
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<Profile xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
        f"<Name>Current</Name><GitHub /><DevFolder>{folders}</DevFolder>"
        "<Local /><Mods /></Profile>\n"
    )


def ensure_pulsar(c: Client) -> None:
    """Creates the client's Pulsar folder from the machine's Pulsar install on first
    use (new-pulsar-instance.sh), with a renamed launcher. The profile enables only
    Remote, Sections and DirectTransport, Remote and Sections from the working copies.
    """
    if not c.launcher.exists():
        subprocess.run(
            [
                str(WORKSPACE / "notes/pulsar-dev-instances/new-pulsar-instance.sh"),
                str(c.pulsar),
                str(PULSAR_TEMPLATE),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        shutil.copy2(c.pulsar / "Interim.bin", c.launcher)
    legacy = c.pulsar / "Legacy"
    _register_source(
        legacy / "Sources" / "sources.xml", "remote", REMOTE_REPO, "Remote.xml"
    )
    _register_source(
        legacy / "Sources" / "sources.xml", "se-sections", REPO, "Sections.xml"
    )
    (legacy / "Profiles").mkdir(exist_ok=True)
    (legacy / "Profiles" / "Current.xml").write_text(
        _profile(["remote", SECTIONS_ID, "direct-transport"]), encoding="utf-8"
    )


def write_configs(c: Client, sections: dict | None = None) -> None:
    storage = c.appdata / "Storage"
    storage.mkdir(parents=True, exist_ok=True)
    options = "".join(
        f"  <{k}>{v}</{k}>\n"
        for k, v in {**SECTIONS_CONFIG, **(sections or {})}.items()
    )
    (storage / "Sections.cfg").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<Config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema">\n'
        f"{options}</Config>\n",
        encoding="utf-8",
    )
    (c.appdata / "Remote.cfg").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<PluginConfig xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema">\n'
        "  <Enabled>true</Enabled>\n  <ListenIP>127.0.0.1</ListenIP>\n"
        f"  <ListenPort>{c.port}</ListenPort>\n"
        "  <AdminPassword>SpaceEngineers</AdminPassword>\n"
        "  <GridGetRateLimit>1000</GridGetRateLimit>\n  <GridGetBurstSize>2000</GridGetBurstSize>\n"
        "  <GridSetRateLimit>100</GridSetRateLimit>\n  <GridSetBurstSize>200</GridSetBurstSize>\n"
        "</PluginConfig>\n",
        encoding="utf-8",
    )
    # The test world is experimental; a fresh user data folder says it is not
    game_cfg = c.appdata / "SpaceEngineers.cfg"
    if not game_cfg.exists():
        shutil.copy(HOME / ".config/SpaceEngineers/SpaceEngineers.cfg", game_cfg)
    text = re.sub(
        r"(<Key>ExperimentalMode</Key>\s*<Value>\s*<Value[^>]*>)\w+(</Value>)",
        r"\1True\2",
        game_cfg.read_text(encoding="utf-8"),
    )
    game_cfg.write_text(text, encoding="utf-8")


def sections_config(c: Client, key: str) -> str | None:
    match = re.search(
        rf"<{key}>(.*?)</{key}>",
        (c.appdata / "Storage/Sections.cfg").read_text(encoding="utf-8"),
    )
    return match.group(1) if match else None


def prepare_world(world: Path, online: str = "OFFLINE", template: str = SPACE) -> Path:
    """A fresh copy of one of the Remote suite's worlds: creative, copy and paste
    on, no trash removal"""
    if world.exists():
        shutil.rmtree(world)
    world.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(WORLDS / f"{template}.zip") as archive:
        archive.extractall(world.parent)
    (world.parent / template).rename(world)
    for name in ("Sandbox.sbc", "Sandbox_config.sbc"):
        path = world / name
        text = path.read_text(encoding="utf-8")
        for key, value in {
            "SessionName": world.name,
            "GameMode": "Creative",
            "EnableCopyPaste": "true",
            "TrashRemovalEnabled": "false",
            "ExperimentalMode": "true",
            "OnlineMode": online,
        }.items():
            text = re.sub(rf"<{key}>[^<]*</{key}>", f"<{key}>{value}</{key}>", text)
        path.write_text(text, encoding="utf-8")
    return world


# ---------------------------------------------------------------------------
# Processes. Each runs in a session of its own, started through run-test.sh, so
# stopping kills exactly the process group this rig started.
# ---------------------------------------------------------------------------


def _alive(pid_file: Path, marker: str) -> int | None:
    try:
        pid = int(pid_file.read_text().strip())
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
    except (OSError, ValueError):
        return None
    return pid if marker.encode() in cmdline else None


def _start(
    command: list[str], need: float, cwd: Path, log: Path, pid_file: Path, env=None
) -> subprocess.Popen:
    process = subprocess.Popen(
        [str(PARALLEL / "run-test.sh"), str(need), "--", *command],
        cwd=cwd,
        env={**os.environ, **(env or {})},
        stdout=open(log, "w"),
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    pid_file.write_text(str(process.pid))
    return process


def _stop(pid_file: Path, marker: str, timeout: float) -> None:
    pid = _alive(pid_file, marker)
    if pid is None:
        pid_file.unlink(missing_ok=True)
        return
    os.killpg(pid, signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while _alive(pid_file, marker) and time.monotonic() < deadline:
        time.sleep(1)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    pid_file.unlink(missing_ok=True)


def client_running(c: Client) -> bool:
    return _alive(c.pid_file, str(c.launcher)) is not None


def launch(
    c: Client, render: bool = False, extra_args=(), sections: dict | None = None
) -> None:
    if client_running(c):
        raise RuntimeError(f"Client {c.pulsar} is already running")
    ensure_pulsar(c)
    write_configs(c, sections)
    c.log.unlink(missing_ok=True)
    args = [
        "-multiInstance", "-lazySteam", "-noprompt", "-noupdate", "-nosplash",
        "-stablelogs", "-sources", "--no-steam", "-appdata", str(c.appdata),
        "--quality", "minimal", "--resolution", "1280x720", "--no-audio", "--headless",
    ]  # fmt: skip
    if c.client_id:
        args += ["--client-id", str(c.client_id)]
    env = {}
    if not render:
        args.append("--no-render")
        env["PULSAR_NO_RENDER"] = "true"
    args += list(extra_args)
    _start(
        [str(c.launcher), *args],
        NEED_GIB["render" if render else "no-render"],
        c.pulsar,
        c.appdata / "launch.log",
        c.pid_file,
        env,
    )


def stop(c: Client) -> None:
    _stop(c.pid_file, str(c.launcher), 30)


def wait_api(c: Client, timeout: float = 2400.0) -> RemoteAPI:
    """The RAM guard may hold the launch back for up to 30 minutes"""
    api = connect(c)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not client_running(c):
            raise RuntimeError(f"The client exited, see {c.appdata / 'launch.log'}")
        try:
            api.ping()
            return api
        except Exception:  # noqa: BLE001 -- not listening yet
            time.sleep(2)
    raise TimeoutError("The client's Remote API did not come up")


def _message_boxes(api: RemoteAPI) -> list[dict]:
    return [s for s in api.list_screens() if s.get("type") == "MyGuiScreenMessageBox"]


def wait_world(api: RemoteAPI, timeout: float = 600.0) -> None:
    """Waits for the session, clicking OK on message boxes on the way (a bare XML
    world first asks to be loaded from XML)"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(1)
        try:
            boxes = _message_boxes(api)
            for box in boxes:
                api.control_click(text="OK", screen=box["index"])
            if not boxes and api.get_state().get("ready"):
                return
        except Exception:  # noqa: BLE001 -- the API times out while a world loads
            pass
    raise TimeoutError("The test world did not become ready")


def ensure_character(api: RemoteAPI, timeout: float = 300.0) -> None:
    """Respawns, or joins on a server, when the world starts without a character"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if api.get_character().get("state") not in (None, "dead"):
                return
        except Exception:  # noqa: BLE001 -- 503 without a character
            pass
        screens = api.list_screens()
        medical = next(
            (i for i, s in enumerate(screens) if "Medical" in s.get("type", "")), None
        )
        if medical is not None:
            for button in ("Respawn", "Join"):
                try:
                    api.control_click(text=button, screen=medical)
                    break
                except Exception:  # noqa: BLE001 -- the other page of the screen
                    continue
        time.sleep(3)
    raise TimeoutError("No live character")


def focus_gameplay(api: RemoteAPI, timeout: float = 60.0) -> None:
    """Closes everything above the gameplay screen, but lets the loading screen finish"""
    keep = ("MyGuiScreenGamePlay", "MyGuiScreenHudSpace")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        screens = [s.get("type") for s in api.list_screens()]
        extra = [i for i, kind in enumerate(screens) if kind not in keep]
        if not extra and set(keep) <= set(screens):
            return
        time.sleep(0.5)
        if (
            extra
            and "MyGuiScreenLoading" not in screens
            and [s.get("type") for s in api.list_screens()] == screens
        ):
            api.close_screen(extra[-1])
    raise TimeoutError("Could not get back to the gameplay screen")


def start_offline(
    c: Client, render: bool = False, sections: dict | None = None, template: str = SPACE
) -> RemoteAPI:
    """Starts a client and loads a fresh copy of the test world"""
    launch(c, render, sections=sections)
    api = wait_api(c)
    world = prepare_world(c.world, template=template)
    try:
        api.load(str(world))
    except Exception:  # noqa: BLE001 -- the load outlives the HTTP timeout
        pass
    wait_world(api)
    ensure_character(api)
    focus_gameplay(api)
    return api


# ---------------------------------------------------------------------------
# Dedicated server: Magnetar with DirectTransport, no Sections counterpart (SE1-0068)
# ---------------------------------------------------------------------------

MAGNETAR = Path(os.environ.get("SECTIONS_MAGNETAR_DIR", HOME / ".config/Magnetar"))
DS64 = Path(
    os.environ.get(
        "SECTIONS_DS64",
        HOME
        / ".steam/debian-installation/steamapps/common/SpaceEngineersDedicatedServer/DedicatedServer64",
    )
)
DS_CONFIG_TEMPLATE = (
    HOME / ".config/SpaceEngineersDedicated/SpaceEngineers-Dedicated.cfg"
)


def prepare_server(s: Server, admins=()) -> None:
    prepare_world(s.world, online="PUBLIC")
    if not (s.config / "Sources").exists():
        s.config.mkdir(parents=True, exist_ok=True)
        shutil.copytree(MAGNETAR / "Magnetar" / "Sources", s.config / "Sources")
        shutil.copy(MAGNETAR / "Magnetar" / "config.xml", s.config / "config.xml")
    (s.config / "Profiles").mkdir(exist_ok=True)
    (s.config / "Profiles" / "Current.xml").write_text(
        _profile(["direct-transport"]), encoding="utf-8"
    )
    text = DS_CONFIG_TEMPLATE.read_text(encoding="utf-8")
    for tag, value in {
        "IP": "127.0.0.1",
        "ServerPort": s.port,
        "SteamPort": s.steam_port,
        "Administrators": "".join(f"<unsignedLong>{a}</unsignedLong>" for a in admins),
        "ServerName": "Sections Test Server",
        "WorldName": WORLD_NAME,
        "PauseGameWhenEmpty": "false",
        "AutoRestartEnabled": "false",
        "IgnoreLastSession": "true",
        "RemoteApiEnabled": "false",
        "LoadWorld": s.world,
    }.items():
        text, count = re.subn(
            rf"<{tag}>.*?</{tag}>|<{tag} />",
            f"<{tag}>{value}</{tag}>",
            text,
            flags=re.S,
        )
        assert count == 1, tag
    s.data.mkdir(parents=True, exist_ok=True)
    (s.data / "SpaceEngineers-Dedicated.cfg").write_text(text, encoding="utf-8")


def server_running(s: Server) -> bool:
    return _alive(s.pid_file, str(s.config)) is not None


def start_server(s: Server, admins=(), timeout: float = 2400.0) -> None:
    if server_running(s):
        raise RuntimeError(f"Server {s.root} is already running")
    s.root.mkdir(parents=True, exist_ok=True)
    prepare_server(s, admins)
    process = _start(
        [
            str(MAGNETAR / "MagnetarInterim.bin"),
            "-multiInstance", "-stableLogs", "-noimplicitmod", "-consent", "deny",
            "-config", str(s.config), "-ds64", str(DS64), "-path", str(s.data),
        ],  # fmt: skip
        SERVER_NEED_GIB,
        MAGNETAR,
        s.log,
        s.pid_file,
        {"SE_DIRECT_TRANSPORT": "1"},
    )
    deadline = time.monotonic() + timeout
    while "Game ready" not in s.log.read_text(errors="replace"):
        if process.poll() is not None:
            raise RuntimeError(f"The server exited, see {s.log}")
        if time.monotonic() > deadline:
            raise TimeoutError(f"The server did not get ready, see {s.log}")
        time.sleep(2)


def stop_server(s: Server) -> None:
    """SIGTERM makes Magnetar save the world and quit"""
    _stop(s.pid_file, str(s.config), 120)


def join(c: Client, s: Server, name: str, render: bool = False) -> RemoteAPI:
    launch(c, render, ["--connect", f"127.0.0.1:{s.port}", "--client-name", name])
    api = wait_api(c)
    wait_world(api)
    ensure_character(api)
    focus_gameplay(api)
    return api


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    c = client(0)
    if command == "start":
        overrides = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)
        stop(c)
        start_offline(
            c,
            render="--render" in sys.argv,
            sections=overrides,
            template=EARTH if "--earth" in sys.argv else SPACE,
        )
        print(f"Ready: SE_REMOTE_URL={c.url}")
    elif command == "stop":
        stop(c)
    else:
        sys.exit(__doc__)
