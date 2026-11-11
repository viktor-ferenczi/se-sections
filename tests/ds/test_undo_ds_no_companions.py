"""Sections and Undo on a client of a dedicated server that runs neither
companion (SE-606): both plugins stay off for editing, as they did before, and
nothing fails. Section editing is refused on the client, Ctrl-Z does not touch
the world.

SECTIONS_SLOT=<n> uv run pytest tests/ds/test_undo_ds_no_companions.py
"""

import time

import rig
import undo_steps as u
from companion import NOT_SERVED, log_has, wait_until

COMPANION = False
UNDO_SERVER = False
UNDO_CLIENT = True

UNDO_OFF = "The server does not run the Undo companion"


def test_both_off(game):
    client = rig.client(1)
    wait_until(lambda: log_has(client, UNDO_OFF), "Undo saying it is off", 60)
    wait_until(lambda: log_has(client, NOT_SERVED), "Sections saying it is off", 60)

    game.cut(*u.TARGET_ROW, ctrl=True)
    game.leave_screens()
    time.sleep(3)
    assert u.exist(game, u.TARGET_CELLS), "Sections cut without its companion"

    game.press("Z", ["LeftControl"])
    time.sleep(3)
    assert u.exist(game, u.TARGET_CELLS)
    assert not (game.server.data / "Undo").exists()
    log = client.log.read_text(errors="replace")
    assert "Recording a removal in Undo failed" not in log
    assert "Undo: Error" not in log
