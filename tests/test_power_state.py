"""Functional blocks keep their on/off state, and the enabled ones work, after
a cut and paste back onto the same powered grid (viktor-ferenczi/se-sections#16).

Run against an isolated client: SECTIONS_SLOT=<n> uv run pytest tests
"""

import time

import harness as h
from harness import OWNERS

# From the timer to the event controller, aimed at from +Z. Remote's aim ray
# passes through the sensor, so it is not a corner.
ROW = (OWNERS["Timer"][0], OWNERS["Event"][0])
# The timer is switched off before the cut, the others stay on
EXPECTED = {"Timer": (False, False), "Sensor": (True, True), "Event": (True, True)}


def states(game) -> dict[str, tuple[bool, bool]]:
    """Whether each block is on, and whether it works"""
    result = {}
    for name in EXPECTED:
        cell = OWNERS[name][0]
        on = game.api.get_property(game.grid, cell, "OnOff")["value"]
        result[name] = (on, game.api.get_block(game.grid, cell)["isWorking"])
    return result


def test_on_off_state_kept(game):
    game.api.set_property(game.grid, OWNERS["Timer"][0], "OnOff", False)
    time.sleep(0.5)
    assert states(game) == EXPECTED
    game.cut(*ROW)
    assert not game.exists(OWNERS["Sensor"][0])
    game.paste_on((ROW[1][0], 0, 0))
    assert game.exists(OWNERS["Sensor"][0])
    # Give a lost state time to show
    time.sleep(5)
    assert states(game) == EXPECTED
    named = h.blocks(game.saved_grids().values())
    assert {name: named[name].findtext("Enabled") for name in EXPECTED} == {
        "Timer": "false",
        "Sensor": "true",
        "Event": "true",
    }
