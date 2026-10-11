"""Timer, sensor and camera blocks as selection corners
(viktor-ferenczi/se-sections#11). Sensors and cameras have no physics: the aim
ray passes through them and hits the block they are mounted on.

Run against an isolated client: SECTIONS_SLOT=<n> uv run pytest tests
"""

import time

import pytest

from harness import OWNERS, TARGETS

TIMER, SENSOR = OWNERS["Timer"][0], OWNERS["Sensor"][0]
CAMERA, BATTERY = TARGETS["Camera"][0], TARGETS["Battery A"][0]
# The timer's buttons face -Z; the sensor and the camera are mounted facing up
FRONT, TOP, BACK = (0, 0, -1), (0, 1, 0), (0, 0, 1)


def look_at(game, cell, side) -> None:
    """Looks at a block from 7 m along a grid axis. Remote's ray passes through
    sensors and cameras, so unlike Game.aim, a hit on the block behind is fine."""
    behind = tuple(c - s for c, s in zip(cell, side))
    for _ in range(3):
        target, direction, _ = game.axis(cell, side)
        game.look_from([t + 7 * d for t, d in zip(target, direction)], target)
        time.sleep(0.5)
        hit = game.api.get_character_target(15)
        if tuple((hit.get("block") or {}).get("min", ())) in (cell, behind):
            return
    raise AssertionError((cell, hit))


@pytest.mark.parametrize(
    "first, first_side, second, second_side",
    [
        (TIMER, FRONT, SENSOR, TOP),
        (SENSOR, TOP, TIMER, FRONT),
        (CAMERA, TOP, BATTERY, BACK),
        (BATTERY, BACK, CAMERA, TOP),
    ],
)
def test_corner_blocks(game, first, first_side, second, second_side):
    """Cuts the row between two blocks, each looked at from the given side. The
    floor under the row must stay."""
    look_at(game, first, first_side)
    game.press("NumPad0")
    game.mouse("left")
    look_at(game, second, second_side)
    game.mouse("left")
    game.mouse("right")
    time.sleep(1)
    row = range(min(first[0], second[0]), max(first[0], second[0]) + 1)
    assert [x for x in row if game.exists((x, 1, 0))] == []
    assert [x for x in row if not game.exists((x, 0, 0))] == []
