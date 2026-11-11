"""A friends game: client 1 of the slot hosts the test world as a lobby, client 2
joins it, both over DirectTransport, without Steam. Both run Sections and Undo.

The host edits its own grids as offline. The joined player, promoted to admin in
the host's world, is served by the host: Sections' companion code carries out its
section editing, Undo's records and replays its steps.

Needs SECTIONS_SLOT. SECTIONS_KEEP=1 leaves both clients running after the run.
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
HOST, JOINER = rig.client(1), rig.client(2)


class HostGame(harness.Game):
    """The host. Escape opens the game menu without pausing in multiplayer, so the
    offline way of closing it misses."""

    def leave_screens(self) -> None:
        self.press("Escape")
        rig.focus_gameplay(self.api)


class JoinedGame(HostGame):
    """The joined client. The world is saved by the host and read from its folder."""

    def __init__(self, api, host_api):
        super().__init__(api)
        self.host = HostGame(host_api)

    def save(self) -> ET.Element:
        return self.host.save()

    def saved_grids(self, root: ET.Element | None = None) -> dict[int, ET.Element]:
        visible = {g["entityId"] for g in self.api.list_grids()}
        return {k: v for k, v in super().saved_grids(root).items() if k in visible}


@pytest.fixture(scope="module")
def host_api():
    for c in (JOINER, HOST):
        rig.stop(c)
    try:
        yield rig.start_lobby_host(
            HOST, promoted={JOINER.client_id: "Admin"}, undo=True
        )
    finally:
        if not KEEP:
            for c in (JOINER, HOST):
                rig.stop(c)


@pytest.fixture(scope="module")
def join_api(host_api):
    api = rig.join_lobby(JOINER, "SectionsJoiner", undo=True)
    # Sections asks the host for its grants once the world is up
    time.sleep(5)
    return api


@pytest.fixture
def host_game(host_api):
    game = HostGame(host_api)
    game.spawn("Sections lobby host")
    yield game
    game.leave_screens()
    game.cleanup()


@pytest.fixture
def join_game(join_api, host_api):
    game = JoinedGame(join_api, host_api)
    game.spawn("Sections lobby joiner")
    yield game
    game.leave_screens()
    game.cleanup()
