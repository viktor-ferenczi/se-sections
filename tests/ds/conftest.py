"""A Magnetar dedicated server (DirectTransport) and Sections clients joined to it.

Each test module gets a fresh server. Module attributes choose what it runs:

- COMPANION: True starts the Sections server companion, compiled from this
  working copy (SectionsServer.xml). False is a vanilla server.
- SERVER_CONFIG: overrides for the companion's Sections.cfg.
- WORLD: overrides for the world settings, like {"GameMode": "Survival"}.
- CLIENT_SETTINGS: Sections settings of Alice's client, on top of the rig's.

Client 1 of the slot joins as Alice, an admin with creative tools on. Client 2
joins as Bob, a space master (the test rig teleports him), only for the tests
that ask for `bob`.

Needs SECTIONS_SLOT: the server and the clients use slot resources ds0, c1 and
c2, so these tests can run beside the offline ones on c0.
SECTIONS_KEEP=1 leaves everything running after the run.
"""

from __future__ import annotations

import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import harness  # noqa: E402
import rig  # noqa: E402

KEEP = os.environ.get("SECTIONS_KEEP") == "1"
ALICE, BOB = "SectionsTester", "SectionsBob"


class ServedGame(harness.Game):
    """A client of the dedicated server. The world is saved on the server (the
    admin's !save chat command of Magnetar) and read from the server's folder."""

    def __init__(self, api, server: rig.Server, client: rig.Client):
        super().__init__(api)
        self.server = server
        self.client = client

    def leave_screens(self) -> None:
        """Escape opens the game menu on a server client without pausing the
        game, so the offline way of closing it misses"""
        self.press("Escape")
        rig.focus_gameplay(self.api)

    def save(self) -> ET.Element:
        sandbox = self.server.world / "SANDBOX_0_0_0_.sbs"
        before = sandbox.stat().st_mtime if sandbox.exists() else 0
        self.api.send_chat("!save")
        deadline = time.monotonic() + 120
        while not sandbox.exists() or sandbox.stat().st_mtime == before:
            assert time.monotonic() < deadline, "The server did not save"
            time.sleep(0.5)
        # Written in place; parse once it stops growing
        while True:
            size = sandbox.stat().st_size
            time.sleep(1)
            if sandbox.stat().st_size == size:
                try:
                    return ET.parse(sandbox).getroot()
                except ET.ParseError:
                    pass

    def saved_grids(self, root: ET.Element | None = None) -> dict[int, ET.Element]:
        """Only the grids this client sees: the server's save also has grids
        that never reached the client, so they are missing from `before`"""
        visible = {g["entityId"] for g in self.api.list_grids()}
        return {k: v for k, v in super().saved_grids(root).items() if k in visible}

    def status(self) -> dict:
        """What the server's companion keeps for this player"""
        return rig.server_status(self.server).get(self.client.client_id, {})


def _module_option(request, name, default):
    return getattr(request.module, name, default)


@pytest.fixture(scope="module")
def server(request):
    s = rig.server(0)
    for i in (1, 2):
        rig.stop(rig.client(i))
    rig.stop_server(s)
    try:
        rig.start_server(
            s,
            admins=[rig.client(1).client_id],
            # Bob may teleport, which takes a space master
            promoted={rig.client(2).client_id: "SpaceMaster"},
            companion=_module_option(request, "COMPANION", False),
            config=_module_option(request, "SERVER_CONFIG", None),
            world=_module_option(request, "WORLD", None),
        )
        yield s
    finally:
        if not KEEP:
            for i in (1, 2):
                rig.stop(rig.client(i))
            rig.stop_server(s)


@pytest.fixture(scope="module")
def api(server, request):
    api = rig.join(
        rig.client(1),
        server,
        ALICE,
        render=True,
        sections=_module_option(request, "CLIENT_SETTINGS", None),
    )
    api.set_admin_flag("creativeTools", True)
    return api


@pytest.fixture(scope="module")
def bob_api(server, api):
    return rig.join(rig.client(2), server, BOB, render=True)


@pytest.fixture
def game(api, server, request):
    game = ServedGame(api, server, rig.client(1))
    game.spawn(f"Sections {request.node.name}"[:60])
    yield game
    game.leave_screens()
    game.cleanup()


@pytest.fixture
def bob(bob_api, server):
    """Bob, without a ship of his own"""
    game = ServedGame(bob_api, server, rig.client(2))
    game.before = {g["entityId"] for g in bob_api.list_grids()}
    yield game
    game.leave_screens()
