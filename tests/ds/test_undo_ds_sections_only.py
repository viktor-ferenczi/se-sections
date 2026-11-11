"""Sections and Undo on a client of a dedicated server that runs the Sections
companion but not Undo's (SE-606). Section editing works, Undo stays off: nothing
is recorded and Ctrl-Z does not bring the blocks back.

SECTIONS_SLOT=<n> uv run pytest tests/ds/test_undo_ds_sections_only.py
"""

import time

import rig
import undo_steps as u
from companion import SERVED, log_has, wait_until

COMPANION = True
UNDO_SERVER = False
UNDO_CLIENT = True

UNDO_OFF = "The server does not run the Undo companion"


def test_sections_without_undo(game):
    client = rig.client(1)
    wait_until(lambda: log_has(client, UNDO_OFF), "Undo saying it is off", 60)
    wait_until(lambda: log_has(client, SERVED), "Sections being served", 60)

    game.cut(*u.TARGET_ROW, ctrl=True)
    game.leave_screens()
    u.wait_until(lambda: u.gone(game, u.TARGET_CELLS), "the cut")

    game.press("Z", ["LeftControl"])
    time.sleep(3)
    assert u.gone(game, u.TARGET_CELLS), "Something undid the cut"
    assert not (game.server.data / "Undo").exists()
    log = game.server.log.read_text(errors="replace")
    assert "Recording a removal in Undo failed" not in log
