"""Steps shared by the server companion tests: raw protocol messages, a wall to
hide parts of, aiming and flying through it."""

from __future__ import annotations

import struct
import time

import rig
from conftest import ServedGame

# Shared/Companion/Protocol.cs
CHANNEL = 48772
EDIT, HIDE = 4, 7
COPY, CUT, DELETE = 1, 2, 3

SERVED = "Sections: Info: Served by the server's Sections companion"
NOT_SERVED = "The server does not run the Sections companion"

# A 5 x 5 armor wall in the XY plane, a battery powering a light next to it
WALL_BATTERY, WALL_LIGHT, WALL_ABOVE_LIGHT = (5, 0, 0), (5, 1, 0), (5, 2, 0)
DOORWAY = ((2, 1, 0), (2, 3, 0))


def _block(pos, kind="CubeBlock", subtype="LargeBlockArmorBlock", extra=""):
    x, y, z = pos
    return (
        f'<MyObjectBuilder_CubeBlock xsi:type="MyObjectBuilder_{kind}">'
        f'<SubtypeName>{subtype}</SubtypeName><Min x="{x}" y="{y}" z="{z}" />'
        '<BlockOrientation Forward="Forward" Up="Up" />'
        f'<ColorMaskHSV x="0.55" y="0.4" z="0.2" />{extra}</MyObjectBuilder_CubeBlock>'
    )


def wall(name: str) -> str:
    blocks = [_block((x, y, 0)) for x in range(5) for y in range(5)]
    blocks.append(
        _block(
            WALL_BATTERY,
            "BatteryBlock",
            "LargeBlockBatteryBlock",
            "<CurrentStoredPower>3</CurrentStoredPower>",
        )
    )
    blocks.append(_block(WALL_LIGHT, "InteriorLight", "SmallLight"))
    blocks.append(_block(WALL_ABOVE_LIGHT))
    return (
        '<?xml version="1.0"?><Definitions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<ShipBlueprints><ShipBlueprint xsi:type="MyObjectBuilder_ShipBlueprintDefinition">'
        f'<Id Type="MyObjectBuilder_ShipBlueprintDefinition" Subtype="{name}" />'
        "<CubeGrids><CubeGrid><GridSizeEnum>Large</GridSizeEnum><IsStatic>false</IsStatic>"
        '<PositionAndOrientation><Position x="0" y="0" z="0" />'
        '<Forward x="0" y="0" z="-1" /><Up x="0" y="1" z="0" /></PositionAndOrientation>'
        f"<CubeBlocks>{''.join(blocks)}</CubeBlocks><DisplayName>{name}</DisplayName>"
        "</CubeGrid></CubeGrids></ShipBlueprint></ShipBlueprints></Definitions>"
    )


def wait_until(predicate, what: str, timeout: float = 30.0):
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:
            return value
        assert time.monotonic() < deadline, f"Timed out waiting for {what}"
        time.sleep(0.5)


def log_has(client: rig.Client, text: str) -> bool:
    return text in client.log.read_text(errors="replace")


# --- raw messages, as a modified client could send them -----------------------


def edit_message(operation: int, grid: int, box_min, box_max) -> bytes:
    # type, request id, operation, grid, box, intersecting, no origin, empty size text
    return (
        struct.pack(
            "<BiBq3i3i??", EDIT, 9999, operation, grid, *box_min, *box_max, False, False
        )
        + b"\x00"
    )


def hide_message(grid: int, cells, hide: bool = True) -> bytes:
    return struct.pack("<Bq?i", HIDE, grid, hide, len(cells)) + b"".join(
        struct.pack("<3i", *cell) for cell in cells
    )


# --- the server's view ----------------------------------------------------------


def hidden_cells(game: ServedGame, grid: int) -> set[tuple[int, int, int]]:
    return {tuple(c) for c in game.status().get("hidden", {}).get(str(grid), [])}


# --- aiming and moving ------------------------------------------------------------


def target(
    game: ServedGame, cell, grid: int | None = None, distance: float = 7
) -> dict:
    """What the client's aim ray hits looking at a cell from +Z"""
    center, direction, _ = game.axis(cell, (0, 0, 1), grid)
    game.look_from([c + distance * d for c, d in zip(center, direction)], center)
    return game.api.get_character_target(15)


def hits(game: ServedGame, cell, grid: int | None = None) -> bool:
    hit = target(game, cell, grid)
    block = hit.get("block") or {}
    return bool(hit.get("hit")) and tuple(block.get("min", ())) == tuple(cell)


def fly_through(game: ServedGame, cell, grid: int | None = None) -> dict:
    """Flies straight at `cell` from 3 cells in front of it (+Z), on forward
    thrust alone, so nothing steers around the wall. Returns the character's cell
    Z afterwards, once the server had time to correct a prediction it does not
    agree with: below -1 when it passed, above 0 when the wall stopped it."""
    x, y, _ = cell
    game.api.character_teleport(*game.world((x, y, 3), grid))
    time.sleep(1)
    game.api.character_look_at(*game.world((x, y, -3), grid), tolerance=0.5)
    game.api.set_input_state(keys=["W"], mode="override")
    time.sleep(3)
    game.api.clear_input_state()
    time.sleep(3)
    position = [float(p) for p in game.api.get_character()["position"]]
    return {"z": cell_z(game, position, grid), "position": position}


def cell_z(game: ServedGame, position, grid: int | None = None) -> float:
    """Z of a world position in the grid's cells"""
    zero = game.world((0, 0, 0), grid)
    one = game.world((0, 0, 1), grid)
    axis = [b - a for a, b in zip(zero, one)]
    size2 = sum(a * a for a in axis)
    return sum((p - z) * a for p, z, a in zip(position, zero, axis)) / size2
