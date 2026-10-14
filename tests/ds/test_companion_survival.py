"""The Sections companion with its default access levels, in a survival world:
only admins may edit or remove collision, and both need creative tools. Also
the hidden block limit (4 here), the blueprint name dialog on Alice's client,
and a client speaking another protocol version.

SECTIONS_SLOT=<n> uv run pytest tests/ds/test_companion_survival.py
"""

import struct
import time

import pytest

import rig
from companion import (
    CHANNEL,
    log_has_server,
    DELETE,
    DOORWAY,
    SERVED,
    edit_message,
    hidden_cells,
    hide_message,
    hits,
    log_has,
    wait_until,
    wall,
)
from conftest import ServedGame
from harness import TARGET_ROW, TARGETS

COMPANION = True
WORLD = {"GameMode": "Survival"}
SERVER_CONFIG = {"MaxHiddenBlocksPerPlayer": "4"}
CLIENT_SETTINGS = {"RenameBlueprint": "true"}

DOORWAY_CELLS = {(2, 1, 0), (2, 2, 0), (2, 3, 0)}


@pytest.fixture
def wall_game(api, server):
    game = ServedGame(api, server, rig.client(1))
    game.spawn("Sections wall", wall("Sections wall"))
    yield game
    game.api.set_admin_flag("creativeTools", True)
    game.press("H", ["LeftControl", "LeftShift"])
    game.leave_screens()
    game.cleanup()


def grants(game) -> tuple:
    status = game.status()
    return status.get("edit"), status.get("cutaway"), status.get("anyGrid")


def test_only_the_admin_is_granted(wall_game, bob):
    wait_until(lambda: log_has(rig.client(2), SERVED), "Bob to be served")
    assert wait_until(lambda: grants(wall_game) == (True, True, True), "Alice's grants")
    assert wait_until(lambda: grants(bob) == (False, False, False), "Bob's grants")


def test_server_refuses_bob(wall_game, bob):
    bob.api.send_mod_message(
        CHANNEL, hide_message(wall_game.grid, sorted(DOORWAY_CELLS))
    )
    bob.api.send_mod_message(
        CHANNEL, edit_message(DELETE, wall_game.grid, (0, 0, 0), (4, 4, 0))
    )
    time.sleep(3)
    assert not hidden_cells(bob, wall_game.grid)
    assert all(wall_game.exists((x, 2, 0)) for x in range(5))


def test_losing_creative_tools_restores_collision(wall_game):
    game = wall_game
    game.select(*DOORWAY)
    game.press("H")
    game.press("Escape")
    wait_until(
        lambda: hidden_cells(game, game.grid) == DOORWAY_CELLS, "the hidden doorway"
    )
    assert not hits(game, (2, 2, 0))

    game.api.set_admin_flag("creativeTools", False)
    wait_until(lambda: grants(game) == (False, False, True), "the grants to drop")
    wait_until(lambda: not hidden_cells(game, game.grid), "the server to drop them")
    # The admin may still hide visually, without removing collision
    wait_until(lambda: hits(game, (2, 2, 0)), "collision back on the client")

    game.api.set_admin_flag("creativeTools", True)
    wait_until(lambda: grants(game) == (True, True, True), "the grants back")


def test_hidden_block_limit(wall_game):
    game = wall_game
    game.select((0, 0, 0), (4, 1, 0))
    game.press("H")
    game.press("Escape")
    wait_until(lambda: len(hidden_cells(game, game.grid)) == 4, "four hidden blocks")
    time.sleep(3)
    assert len(hidden_cells(game, game.grid)) == 4
    assert log_has_server(game.server, "reached the limit of hidden blocks")


def test_blueprint_name_dialog(game):
    """The name dialog opens once the grids are back from the server"""
    name = f"Sections named {int(time.time())}"
    folder = rig.client(1).appdata / "Blueprints" / "local" / "Sections" / name
    game.select(*TARGET_ROW)
    game.press("Enter", ["LeftControl"])
    api = game.api
    wait_until(
        lambda: any(s.get("type") == "NameDialog" for s in api.list_screens()),
        "the name dialog",
    )
    index = next(
        i for i, s in enumerate(api.list_screens()) if s.get("type") == "NameDialog"
    )
    box = next(c for c in api.get_controls(index) if c["type"] == "MyGuiControlTextbox")
    api.control_set(box["name"], name, screen=index)
    api.control_click(text="OK", screen=index)
    bp = wait_until(
        lambda: (folder / "bp.sbc").exists() and folder / "bp.sbc", "the file", 60
    )
    text = bp.read_text(encoding="utf-8")
    for block in TARGETS:
        assert f"<CustomName>{block}</CustomName>" in text, block
    game.leave_screens()


def test_other_protocol_version_is_not_served(bob):
    """Last: Bob's client stays unserved afterwards"""
    bob.api.send_mod_message(CHANNEL, struct.pack("<Bi", 1, 999))
    wait_until(
        lambda: log_has_server(bob.server, "speaks Sections protocol 999, not served"),
        "the server to refuse the hello",
    )
    wait_until(
        lambda: log_has(rig.client(2), "the server runs another version of Sections"),
        "Bob's client to hear it",
    )
