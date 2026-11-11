"""Sections and Undo on a client of a dedicated server that runs the Undo
companion but not Sections' (SE-606). Undo works for what the game does, section
editing stays off on the client.

SECTIONS_SLOT=<n> uv run pytest tests/ds/test_undo_ds_undo_only.py
"""

import time

import rig
import undo_steps as u
from companion import NOT_SERVED, log_has, wait_until

COMPANION = False
UNDO_SERVER = True
UNDO_CLIENT = True


def history(game):
    return u.History(
        game.server.data / "Undo" / "status-players.json", game.client.client_id
    )


def test_undo_without_sections(game):
    client = rig.client(1)
    wait_until(lambda: log_has(client, NOT_SERVED), "Sections saying it is off", 60)

    game.cut(*u.TARGET_ROW, ctrl=True)
    game.leave_screens()
    time.sleep(3)
    assert u.exist(game, u.TARGET_CELLS), "Sections cut without its companion"

    # A grid delete through the player's close request is one step
    grids = lambda: {g["entityId"] for g in game.api.list_grids()}  # noqa: E731
    game.api.close_grid(game.grid)
    u.wait_until(lambda: game.grid not in grids(), "the grid closed")
    node = u.wait_until(history(game).current, "the delete in the history")
    u.undo(game, history(game), node)
    u.wait_until(lambda: game.grid in grids(), "the grid back")
