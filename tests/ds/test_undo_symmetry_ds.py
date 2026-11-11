"""Sections with the Undo plugin and symmetry planes on the grid (SE-1359), on a
dedicated server running both companions: a cut, a delete, a cut pasted back and a
paste into the grid are each one Undo step, whatever planes cross the selection,
and undo and redo take every block back and do it again with its references
intact.

SECTIONS_SLOT=<n> uv run pytest tests/ds/test_undo_symmetry_ds.py
"""

import pytest

import undo_steps as u

COMPANION = True
UNDO_SERVER = True
UNDO_CLIENT = True


def history(game):
    return u.History(
        game.server.data / "Undo" / "status-players.json", game.client.client_id
    )


@pytest.fixture(params=list(u.PLANE_SETUPS), autouse=True)
def planes(request, game):
    yield u.PLANE_SETUPS[request.param]
    u.symmetry_off(game)


def test_cut(game, planes):
    u.set_planes(game, planes(u.TARGET_MID))
    u.cut_undo_redo(game, history(game))


def test_delete(game, planes):
    u.set_planes(game, planes(u.OWNER_MID))
    u.delete_undo_redo(game, history(game))


def test_cut_and_paste_back(game, planes):
    u.set_planes(game, planes(u.TARGET_MID))
    u.cut_paste_back_undo(game, history(game))


def test_paste_into_grid(game, planes):
    u.set_planes(game, planes(u.TARGET_MID))
    u.paste_into_grid(game, history(game))
