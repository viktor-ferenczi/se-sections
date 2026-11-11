"""Sections with the Undo plugin in a friends game (SE-606), as the lobby host and
as the joined client. The host records its own steps in its history, like
offline. The joined player's section editing runs on the host, which records it
in the history it keeps for that player; the player's Ctrl-Z and Ctrl-Y replay it
there.

SECTIONS_SLOT=<n> uv run pytest tests/lobby
"""

import undo_steps as u
from conftest import HOST, JOINER


def host_history():
    return u.History(HOST.appdata / "Undo" / "status.json")


def joiner_history():
    return u.History(HOST.appdata / "Undo" / "status-players.json", JOINER.client_id)


def test_host_cut(host_game):
    u.cut_undo_redo(host_game, host_history())


def test_host_delete(host_game):
    u.delete_undo_redo(host_game, host_history())


def test_joiner_cut(join_game):
    u.cut_undo_redo(join_game, joiner_history())


def test_joiner_delete(join_game):
    u.delete_undo_redo(join_game, joiner_history())


def test_joiner_cut_and_paste_back(join_game):
    u.cut_paste_back_undo(join_game, joiner_history())


def test_joiner_cut_rotor_with_head(join_game):
    u.cut_rotor_with_head(join_game, joiner_history())
