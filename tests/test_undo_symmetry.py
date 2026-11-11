"""Sections with the Undo plugin and symmetry planes on the grid (SE-1359), offline:
a cut, a delete, a cut pasted back and a paste into the grid are each one Undo
step, whatever planes cross the selection, and undo and redo take every block back
and do it again with its references intact. Sections ignores symmetry; the planes
must not make the game or Undo mirror anything either.

SECTIONS_SLOT=<n> uv run pytest tests/test_undo_symmetry.py
"""

import pytest

import rig
import undo_steps as u

UNDO = True


def history(game):
    return u.History(rig.client(0).appdata / "Undo" / "status.json")


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
