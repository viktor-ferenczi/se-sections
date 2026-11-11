"""Sections with the Undo plugin offline (SE-606): a cut or a delete is one step in
Undo's history, Ctrl-Z puts the blocks back as they were and Ctrl-Y removes them
again. Without Undo the other test modules run Sections alone.

SECTIONS_SLOT=<n> uv run pytest tests/test_undo.py
"""

import rig
import undo_steps as u

UNDO = True


def history(game):
    return u.History(rig.client(0).appdata / "Undo" / "status.json")


def test_cut(game):
    u.cut_undo_redo(game, history(game))


def test_delete(game):
    u.delete_undo_redo(game, history(game))


def test_cut_and_paste_back(game):
    u.cut_paste_back_undo(game, history(game))


def test_cut_rotor_with_head(game):
    u.cut_rotor_with_head(game, history(game))
