"""The Sections companion with its default access levels, in a survival world:
only admins may edit or remove collision, and both need creative tools.

SECTIONS_SLOT=<n> uv run pytest tests/ds/test_companion_survival.py
"""

import time

import pytest

import rig
from companion import (
    CHANNEL,
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

COMPANION = True
WORLD = {"GameMode": "Survival"}

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
