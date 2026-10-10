"""A Sections client on a vanilla dedicated server.

Section editing (copy, cut, delete, blueprint, clearing the reference data)
runs only offline or on the host, so a client of a dedicated server cannot
cut a section, and nothing restores references there until Sections has a
server counterpart (se1/tickets/SE1-0068.md). These tests pin that down.

SECTIONS_SLOT=<n> uv run pytest tests/ds
"""

import time

import rig
from harness import TARGET_ROW, TARGETS


def test_client_runs_sections(api):
    assert api.get_state()["multiplayer"] != "offline"
    client = rig.client(1)
    pulsar_log = (client.pulsar / "Legacy" / "info.log").read_text(errors="replace")
    assert f"Sections ({rig.SECTIONS_ID})" in pulsar_log
    game_log = client.log.read_text(errors="replace")
    assert "ClientPlugin.Logic" not in game_log, "Sections threw an exception"


def test_editing_is_refused_on_a_client(game):
    """Copy, cut and delete do nothing; the blocks stay and nothing gets onto
    the clipboard"""
    second = TARGET_ROW[1]
    game.aim(second)
    game.press("NumPad0")
    game.press("Delete")  # cut the aimed block
    game.press("Escape")
    assert game.exists(second)

    game.cut(*TARGET_ROW, ctrl=True)
    time.sleep(1)
    assert all(game.exists(pos) for pos, _, _ in TARGETS.values())
    game.press("Back")
    time.sleep(1)
    assert all(game.exists(pos) for pos, _, _ in TARGETS.values())
    game.leave_screens()

    # A click into empty space would paste a copy if one had been made
    game.copy(*TARGET_ROW)
    game.leave_screens()
    assert not game.paste_free()
