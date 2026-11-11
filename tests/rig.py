"""Isolated test clients and server for the Sections tests.

Everything a run uses comes from a parallel test slot of the workspace
(se/testing/parallel-test-work/README.md), so several sessions can test at once:

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

import json
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
# A worktree outside the workspace names it with SE_WORKSPACE
WORKSPACE = Path(os.environ.get("SE_WORKSPACE", REPO.parents[2]))
PARALLEL = WORKSPACE / "testing" / "parallel-test-work"

sys.path.insert(0, str(REMOTE_REPO / "skills" / "se-remote"))
from se_remote import RemoteAPI  # noqa: E402

SECTIONS_ID = "viktor-ferenczi/se-sections"
SERVER_ID = ET.parse(REPO / "SectionsServer.xml").getroot().findtext("Id")
# The Undo plugin's working copy, for the tests of Sections with Undo (SE-606).
# Its client and server manifests share one id.
UNDO_REPO = Path(os.environ.get("SECTIONS_UNDO_REPO", PLUGINS / "se-undo"))
UNDO_ID = "AC284074-A676-4930-B47A-F30450988608"
# Undo's status files (status.json, status-players.json) for the tests to read
UNDO_CONFIG = {"DebugStatusFile": "true", "LogLevel": "Debug"}
PULSAR_TEMPLATE = Path(
    os.environ.get("SECTIONS_PULSAR_TEMPLATE", HOME / ".config/Pulsar")
)
# The Remote suite's worlds. The fixture tests use the space world; the older
# scripts expect the upright character of the Earth world.
WORLDS = REMOTE_REPO / "Worlds"
SPACE, EARTH = "RemoteAPITestSpace", "RemoteAPITestEarthPlanet"
WORLD_NAME = "SectionsTest"
LAUNCHER = "SectionsInterim.bin"

# RSS of one client, settled in a world, for the RAM guard (README.md, section 3)
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
        raise RuntimeError(f"Slot {value} is not claimed, see {PARALLEL / 'README.md'}")
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
    # A paste or a flight on a server client takes longer than Remote's default 10 s
    return RemoteAPI(
        (c or client(0)).url, username="admin", password="SpaceEngineers", timeout=60
    )


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


def ensure_pulsar(c: Client, undo: bool = False) -> None:
    """Creates the client's Pulsar folder from the machine's Pulsar install on first
    use (new-pulsar-instance.sh), with a renamed launcher. The profile enables only
    Remote, Sections and DirectTransport, Remote and Sections from the working copies,
    and with `undo` the Undo plugin from its working copy too.
    """
    if not c.launcher.exists():
        subprocess.run(
            [
                str(WORKSPACE / "testing/pulsar-dev-instances/new-pulsar-instance.sh"),
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
    if undo:
        _register_source(
            legacy / "Sources" / "sources.xml", "se-undo", UNDO_REPO, "Undo.xml"
        )
    (legacy / "Profiles").mkdir(exist_ok=True)
    (legacy / "Profiles" / "Current.xml").write_text(
        _profile(
            ["remote", SECTIONS_ID, "direct-transport", *([UNDO_ID] if undo else [])]
        ),
        encoding="utf-8",
    )


def _config_xml(root: str, options: dict) -> str:
    lines = "".join(f"  <{k}>{v}</{k}>\n" for k, v in options.items())
    return f'<?xml version="1.0" encoding="utf-8"?>\n<{root}>\n{lines}</{root}>\n'


def write_configs(c: Client, sections: dict | None = None, undo: bool = False) -> None:
    storage = c.appdata / "Storage"
    storage.mkdir(parents=True, exist_ok=True)
    if undo:
        # A fresh history and grid store for each launch
        shutil.rmtree(c.appdata / "Undo", ignore_errors=True)
        (storage / "Undo.cfg").write_text(
            _config_xml("Config", UNDO_CONFIG), encoding="utf-8"
        )
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


def add_local_mods(c: Client, world: Path, mods) -> None:
    """Copies mod folders into the client's Mods folder and adds them to the world"""
    items = ""
    for mod in map(Path, mods):
        target = c.appdata / "Mods" / mod.name
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(mod, target)
        items += (
            f'<ModItem FriendlyName="{mod.name}"><Name>{mod.name}</Name>'
            "<PublishedFileId>0</PublishedFileId></ModItem>"
        )
    if not items:
        return
    for name in ("Sandbox.sbc", "Sandbox_config.sbc"):
        path = world / name
        text = path.read_text(encoding="utf-8")
        text, count = re.subn(r"<Mods\s*/>", f"<Mods>{items}</Mods>", text)
        assert count == 1, name
        path.write_text(text, encoding="utf-8")


def promote(world: Path, promoted: dict) -> None:
    """Game access levels by Steam id, like {steam_id: "Admin"}"""
    checkpoint = world / "Sandbox.sbc"
    items = "".join(
        f"<item><Key>{k}</Key><Value>{v}</Value></item>" for k, v in promoted.items()
    )
    checkpoint.write_text(
        checkpoint.read_text(encoding="utf-8").replace(
            "</MyObjectBuilder_Checkpoint>",
            f"<PromotedUsers><dictionary>{items}</dictionary></PromotedUsers>"
            "</MyObjectBuilder_Checkpoint>",
            1,
        ),
        encoding="utf-8",
    )


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
    c: Client,
    render: bool = False,
    extra_args=(),
    sections: dict | None = None,
    undo: bool = False,
) -> None:
    if client_running(c):
        raise RuntimeError(f"Client {c.pulsar} is already running")
    ensure_pulsar(c, undo)
    write_configs(c, sections, undo)
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
    c: Client,
    render: bool = False,
    sections: dict | None = None,
    template: str = SPACE,
    undo: bool = False,
    mods=(),
) -> RemoteAPI:
    """Starts a client and loads a fresh copy of the test world. `mods` are folders
    of local mods the world loads."""
    launch(c, render, sections=sections, undo=undo)
    api = wait_api(c)
    world = prepare_world(c.world, template=template)
    add_local_mods(c, world, mods)
    try:
        api.load(str(world))
    except Exception:  # noqa: BLE001 -- the load outlives the HTTP timeout
        pass
    wait_world(api)
    ensure_character(api)
    focus_gameplay(api)
    return api


# ---------------------------------------------------------------------------
# Dedicated server: Magnetar with DirectTransport, with or without the companion
# ---------------------------------------------------------------------------

MAGNETAR = Path(os.environ.get("SECTIONS_MAGNETAR_DIR", HOME / ".config/Magnetar"))
DS64 = Path(
    os.environ.get(
        "SECTIONS_DS64",
        HOME
        / ".steam/debian-installation/steamapps/common/SpaceEngineersDedicatedServer/DedicatedServer64",
    )
)
ERROR_REPORTING = WORKSPACE / "se1" / "plugins" / "error-reporting"
DS_CONFIG_TEMPLATE = (
    HOME / ".config/SpaceEngineersDedicated/SpaceEngineers-Dedicated.cfg"
)


def prepare_server(
    s: Server,
    admins=(),
    companion: bool = False,
    config: dict | None = None,
    world: dict | None = None,
    promoted: dict | None = None,
    undo: bool = False,
) -> None:
    """The companion is compiled from this working copy (SectionsServer.xml as a
    dev folder). `config` overrides its Sections.cfg, `world` the world settings.
    `promoted` gives players a game access level, like {steam_id: "SpaceMaster"}.
    `undo` adds the Undo companion from its working copy (UndoServer.xml)."""
    prepare_world(s.world, online="PUBLIC")
    if promoted:
        promote(s.world, promoted)
    for name in ("Sandbox.sbc", "Sandbox_config.sbc"):
        path = s.world / name
        text = path.read_text(encoding="utf-8")
        for key, value in (world or {}).items():
            text = re.sub(rf"<{key}>[^<]*</{key}>", f"<{key}>{value}</{key}>", text)
        path.write_text(text, encoding="utf-8")
    if not (s.config / "Sources").exists():
        s.config.mkdir(parents=True, exist_ok=True)
        shutil.copytree(MAGNETAR / "Magnetar" / "Sources", s.config / "Sources")
        shutil.copy(MAGNETAR / "Magnetar" / "config.xml", s.config / "config.xml")
    sources = s.config / "Sources" / "sources.xml"
    _register_source(sources, "se-sections", REPO, "SectionsServer.xml")
    # Magnetar's core plugin from the working copy: GitHub rate limits the
    # download of the hub's build now and then, and Magnetar quits without it
    _register_source(sources, "se-undo", UNDO_REPO, "UndoServer.xml")
    dev = [
        "direct-transport",
        *([SERVER_ID] if companion else []),
        *([UNDO_ID] if undo else []),
    ]
    if ERROR_REPORTING.exists():
        _register_source(
            sources, "error-reporting", ERROR_REPORTING, "ErrorReportingServer.xml"
        )
        dev.append("error-reporting")
    (s.config / "Profiles").mkdir(exist_ok=True)
    (s.config / "Profiles" / "Current.xml").write_text(_profile(dev), encoding="utf-8")
    s.data.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(s.data / "Sections", ignore_errors=True)
    shutil.rmtree(s.data / "Undo", ignore_errors=True)
    (s.data / "Undo.cfg").write_text(
        _config_xml("UndoServerConfig", UNDO_CONFIG), encoding="utf-8"
    )
    options = "".join(
        f"  <{k}>{v}</{k}>\n"
        for k, v in {"DebugStatusFile": "true", **(config or {})}.items()
    )
    (s.data / "Sections.cfg").write_text(
        f'<?xml version="1.0" encoding="utf-8"?>\n<SectionsServerConfig>\n{options}</SectionsServerConfig>\n',
        encoding="utf-8",
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
    (s.data / "SpaceEngineers-Dedicated.cfg").write_text(text, encoding="utf-8")


def server_running(s: Server) -> bool:
    return _alive(s.pid_file, str(s.config)) is not None


def start_server(s: Server, admins=(), timeout: float = 2400.0, **options) -> None:
    """`options` go to prepare_server"""
    if server_running(s):
        raise RuntimeError(f"Server {s.root} is already running")
    s.root.mkdir(parents=True, exist_ok=True)
    prepare_server(s, admins, **options)
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


def server_status(s: Server) -> dict:
    """What the companion serves, by Steam id: grants and hidden block positions
    by grid id. Written every second while it changes (DebugStatusFile)."""
    path = s.data / "Sections" / "status-players.json"
    if not path.exists():
        return {}
    for _ in range(5):
        try:
            players = json.loads(path.read_text(encoding="utf-8"))["players"]
            return {int(p["steamId"]): p for p in players}
        except (ValueError, KeyError):
            time.sleep(0.2)
    raise AssertionError(f"Cannot read {path}")


def join(
    c: Client,
    s: Server,
    name: str,
    render: bool = False,
    sections: dict | None = None,
    undo: bool = False,
) -> RemoteAPI:
    launch(
        c,
        render,
        ["--connect", f"127.0.0.1:{s.port}", "--client-name", name],
        sections=sections,
        undo=undo,
    )
    api = wait_api(c)
    wait_world(api)
    ensure_character(api)
    focus_gameplay(api)
    return api


# ---------------------------------------------------------------------------
# Friends game: a client hosts the test world as a lobby, another joins it, both
# over DirectTransport, without Steam (workspace note direct-transport-lobby-rig)
# ---------------------------------------------------------------------------


def lobby_port() -> int:
    """The UDP port of the lobby: server 5's port of the slot, which no test uses"""
    if SLOT is None:
        raise RuntimeError("The lobby tests need SECTIONS_SLOT")
    return 28000 + 10 * SLOT[0] + 5


def start_lobby_host(
    c: Client, promoted: dict | None = None, undo: bool = False
) -> RemoteAPI:
    """Loads a fresh copy of the test world offline and saves it, which writes the
    binary sector a bare XML world lacks, then loads it again as a friends game.
    `promoted` gives joining players an access level; an offline save drops
    promotions, so they go into the saved world."""
    launch(
        c,
        True,
        ["--host-lobby", str(lobby_port()), "--client-name", "SectionsHost"],
        undo=undo,
    )
    api = wait_api(c)
    world = prepare_world(c.world)
    try:
        api.load(str(world))
    except Exception:  # noqa: BLE001 -- the load outlives the HTTP timeout
        pass
    wait_world(api)
    api.save()
    time.sleep(1)
    deadline = time.monotonic() + 120
    while api.get_state()["saving"]:
        if time.monotonic() > deadline:
            raise TimeoutError("The host did not save the world")
        time.sleep(0.5)
    if promoted:
        promote(world, promoted)
    try:
        api.load(str(world), online_mode="FRIENDS", max_players=4)
    except Exception:  # noqa: BLE001 -- the load outlives the HTTP timeout
        pass
    deadline = time.monotonic() + 600
    while True:
        try:
            if api.get_state().get("multiplayer") == "lobby-host":
                break
        except Exception:  # noqa: BLE001 -- the API times out while a world loads
            pass
        if not client_running(c):
            raise RuntimeError(f"The host exited, see {c.appdata / 'launch.log'}")
        if time.monotonic() > deadline:
            raise TimeoutError("The host did not start hosting")
        time.sleep(1)
    wait_world(api)
    ensure_character(api)
    focus_gameplay(api)
    return api


def join_lobby(c: Client, name: str, undo: bool = False) -> RemoteAPI:
    launch(
        c,
        True,
        ["--join-lobby", f"127.0.0.1:{lobby_port()}", "--client-name", name],
        undo=undo,
    )
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
