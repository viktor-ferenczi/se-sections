"""Sections with the Undo plugin and symmetry planes on the grid (SE-1359) in a
friends game, as the lobby host and as the joined client: each section edit is one
step in the history the host keeps, and undo and redo restore it exactly.

SECTIONS_SLOT=<n> uv run pytest tests/lobby/test_undo_symmetry_lobby.py
"""

import pytest

import undo_steps as u
from conftest import HOST, JOINER

STEPS = {
    "cut": (u.TARGET_MID, u.cut_undo_redo),
    "delete": (u.OWNER_MID, u.delete_undo_redo),
    "cut-paste-back": (u.TARGET_MID, u.cut_paste_back_undo),
    "paste-into-grid": (u.TARGET_MID, u.paste_into_grid),
}


def run(game, history, setup: str, step: str) -> None:
    mid, action = STEPS[step]
    u.set_planes(game, u.PLANE_SETUPS[setup](mid))
    try:
        action(game, history)
    finally:
        u.symmetry_off(game)


@pytest.mark.parametrize("step", list(STEPS))
@pytest.mark.parametrize("setup", list(u.PLANE_SETUPS))
def test_host(host_game, setup, step):
    run(host_game, u.History(HOST.appdata / "Undo" / "status.json"), setup, step)


@pytest.mark.parametrize("step", list(STEPS))
@pytest.mark.parametrize("setup", list(u.PLANE_SETUPS))
def test_joiner(join_game, setup, step):
    history = u.History(HOST.appdata / "Undo" / "status-players.json", JOINER.client_id)
    run(join_game, history, setup, step)
