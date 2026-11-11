"""Sections with the Undo plugin on a dedicated server running both companions
(SE-606). Alice's cut or delete runs on the server, which records it in her Undo
history there; Ctrl-Z and Ctrl-Y on her client undo and redo it on the server.

SECTIONS_SLOT=<n> uv run pytest tests/ds/test_undo_ds.py
"""

import undo_steps as u

COMPANION = True
UNDO_SERVER = True
UNDO_CLIENT = True


def history(game):
    return u.History(
        game.server.data / "Undo" / "status-players.json", game.client.client_id
    )


def test_cut(game):
    u.cut_undo_redo(game, history(game))


def test_delete(game):
    u.delete_undo_redo(game, history(game))


def test_cut_and_paste_back(game):
    u.cut_paste_back_undo(game, history(game))


def test_cut_rotor_with_head(game):
    u.cut_rotor_with_head(game, history(game))
