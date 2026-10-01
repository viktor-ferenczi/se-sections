"""Run against a disposable creative world with rendering enabled.

SE_REMOTE_URL=http://127.0.0.1:24188 python tests/test_cutaway.py
Uses the sibling Remote plugin's Python environment.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO.parent / "remote" / "skills" / "se-remote"))
from se_remote import RemoteAPI, OpError, CallOp  # noqa: E402

OUT = Path(os.environ.get("SECTIONS_TEST_OUTPUT", "/tmp/sections-test-results"))
ORIGIN = (600000.0 + time.time() % 10000, 600000.0, 600000.0)
GRID_ID = 0
INCLUDES = os.environ.get("SECTIONS_INCLUDE_INTERSECTING", "0") == "1"


def block(
    pos: tuple[int, int, int],
    kind: str = "CubeBlock",
    subtype: str = "LargeBlockArmorBlock",
    extra: str = "",
) -> str:
    x, y, z = pos
    return (
        f'<MyObjectBuilder_CubeBlock xsi:type="MyObjectBuilder_{kind}">'
        f'<SubtypeName>{subtype}</SubtypeName><Min x="{x}" y="{y}" z="{z}" />'
        '<BlockOrientation Forward="Forward" Up="Up" />'
        f'<ColorMaskHSV x="0.55" y="0.4" z="0.2" />{extra}</MyObjectBuilder_CubeBlock>'
    )


def blueprint() -> str:
    blocks = [block((x, y, 0)) for x in range(5) for y in range(5)]
    blocks += [
        block(
            (5, 0, 0),
            "BatteryBlock",
            "LargeBlockBatteryBlock",
            "<CurrentStoredPower>3</CurrentStoredPower>",
        ),
        block((5, 1, 0), "InteriorLight", "SmallLight"),
        block((5, 2, 0)),
        block((6, 0, 0), "Refinery", "LargeRefinery"),
        block((6, 0, -1)),
        block((6, 4, 0)),
        block((6, 4, 1)),
        block((-1, 0, 0)),
        block((-1, 0, -1)),
        block((7, 4, 1)),
        block((8, 4, 1)),
        block((8, 4, 2)),
    ]
    return (
        '<?xml version="1.0"?><Definitions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<ShipBlueprints><ShipBlueprint xsi:type="MyObjectBuilder_ShipBlueprintDefinition">'
        '<Id Type="MyObjectBuilder_ShipBlueprintDefinition" Subtype="Sections test" />'
        "<CubeGrids><CubeGrid><GridSizeEnum>Large</GridSizeEnum><IsStatic>false</IsStatic>"
        '<PositionAndOrientation><Position x="0" y="0" z="0" />'
        '<Forward x="0" y="0" z="-1" /><Up x="0" y="1" z="0" /></PositionAndOrientation>'
        "<CubeBlocks>"
        + "".join(blocks)
        + "</CubeBlocks><DisplayName>Sections mask test</DisplayName>"
        "</CubeGrid></CubeGrids></ShipBlueprint></ShipBlueprints></Definitions>"
    )


def press(api: RemoteAPI, key: str, modifiers: list[str] | None = None) -> None:
    api.key(key, modifiers, hold_frames=1)
    time.sleep(0.25)


def aim(api: RemoteAPI, cell: tuple[int, int, int]) -> dict:
    target = api.call([CallOp.grid_to_world(GRID_ID, cell)]).call(0)["world"]
    api.character_teleport(
        target[0], target[1] - 1.5, target[2] + (-7 if cell[2] < 0 else 7)
    )
    time.sleep(0.25)
    api.character_look_at(*target)
    time.sleep(0.2)
    return api.get_character_target(15)


def select(
    api: RemoteAPI, first: tuple[int, int, int], second: tuple[int, int, int]
) -> None:
    assert aim(api, first)["hit"], f"No selectable block at {first}"
    press(api, "NumPad0")
    api.click(640, 360)
    time.sleep(0.25)
    assert aim(api, second)["hit"], f"No selectable block at {second}"
    api.click(640, 360)
    time.sleep(0.25)


def mouse_checks(api: RemoteAPI, grid_id: int) -> None:
    for invert in (False, True):
        select(api, (6, 0, -1), (6, 4, 1))
        api.set_input_state(
            keys=["LeftControl"] if invert else None,
            mouse_x=640,
            mouse_y=360,
            mouse_left=True,
            mode="override",
        )
        time.sleep(0.1)
        api.clear_input_state()
        time.sleep(0.5)
        before = {g["entityId"] for g in api.list_grids()}
        api.character_teleport(ORIGIN[0], ORIGIN[1], ORIGIN[2] + 100)
        api.character_look_at(ORIGIN[0], ORIGIN[1], ORIGIN[2] + 90)
        time.sleep(0.5)
        api.click(640, 360)
        time.sleep(1)
        copies = [g for g in api.list_grids() if g["entityId"] not in before]
        assert copies, "Copy clipboard did not paste"
        copied_refinery = any(
            any(
                b["blockType"] == "MyRefinery"
                for b in api.list_blocks(g["entityId"])["blocks"]
            )
            for g in copies
        )
        assert copied_refinery == (INCLUDES ^ invert), (
            INCLUDES,
            invert,
            copied_refinery,
        )
        for g in copies:
            api.close_grid(g["entityId"])
        # A completed paste can keep the clipboard active for another paste.
        press(api, "Escape")
        if api.get_state()["paused"]:
            press(api, "Escape")
        print(f"PASS copy with Ctrl={invert}", flush=True)
    print("PASS copy mouse button honors shared setting and Ctrl inversion", flush=True)
    refinery_id = api.get_block(grid_id, (7, 0, 1))["entityId"]
    select(api, (6, 0, -1), (6, 4, 1))
    api.set_input_state(
        keys=["LeftControl"],
        mouse_x=640,
        mouse_y=360,
        mouse_right=True,
        mode="override",
    )
    time.sleep(0.1)
    api.clear_input_state()
    time.sleep(0.5)
    refinery_present = True
    try:
        api.call([CallOp.fat_block_method(refinery_id, "GetPosition")]).call(0)
    except OpError:
        refinery_present = False
    assert refinery_present == INCLUDES, (INCLUDES, refinery_present)
    press(api, "Escape")
    if api.get_state()["paused"]:
        press(api, "Escape")
    print("PASS cut mouse button inverts shared setting", flush=True)


def copied_mask_check(api: RemoteAPI, grid_id: int) -> None:
    global GRID_ID
    select(api, (1, 0, 0), (1, 4, 0))
    press(api, "H")
    press(api, "Escape")
    assert not aim(api, (1, 2, 0))["hit"]
    select(api, (0, 0, 0), (4, 4, 0))
    api.click(640, 360)
    time.sleep(0.5)
    before = {g["entityId"] for g in api.list_grids()}
    api.character_teleport(ORIGIN[0], ORIGIN[1], ORIGIN[2] + 100)
    api.character_look_at(ORIGIN[0], ORIGIN[1], ORIGIN[2] + 90)
    api.click(640, 360)
    time.sleep(1)
    copies = [g for g in api.list_grids() if g["entityId"] not in before]
    assert len(copies) == 1, copies
    GRID_ID = copies[0]["entityId"]
    assert aim(api, (1, 2, 0))["hit"], "Copied block inherited the source mask"
    GRID_ID = grid_id
    assert not aim(api, (1, 2, 0))["hit"], "Copy changed the source mask"
    api.close_grid(copies[0]["entityId"])
    press(api, "Escape")
    if api.get_state()["paused"]:
        press(api, "Escape")
    press(api, "H", ["LeftControl", "LeftShift"])
    print("PASS copied and pasted grid has no inherited hidden cells", flush=True)


def main() -> None:
    global GRID_ID
    OUT.mkdir(parents=True, exist_ok=True)
    with RemoteAPI(
        os.environ.get("SE_REMOTE_URL", "http://127.0.0.1:24188"),
        username="admin",
        password="SpaceEngineers",
    ) as api:
        assert api.get_state().get("active"), "Load a disposable creative world first"
        if api.get_state()["paused"]:
            press(api, "Escape")
        press(api, "H", ["LeftControl", "LeftShift"])
        if api.get_character().get("controlledEntity"):
            api.character_use()
            time.sleep(0.5)
        assert not api.get_character().get(
            "controlledEntity"
        ), "Leave the seat before testing"
        api.character_teleport(ORIGIN[0], ORIGIN[1], ORIGIN[2] + 20)
        time.sleep(0.5)
        if not api.get_character().get("jetpack"):
            press(api, "X")
        api.character_set_dampeners(True)
        for _ in range(30):
            previous = api.get_character()["position"]
            time.sleep(0.2)
            current = api.get_character()["position"]
            if sum((a - b) ** 2 for a, b in zip(previous, current)) < 0.01:
                break
        else:
            raise AssertionError("Character did not stop before fixture placement")
        pasted = api.paste_blueprint(
            xml=blueprint(), position=ORIGIN, forward=(0, 0, -1), up=(0, 1, 0)
        )
        grid_id = GRID_ID = pasted[0]["entityId"]
        (OUT / "grid.json").write_text(json.dumps(pasted, indent=2))
        time.sleep(1)
        print("Grid created", grid_id, api.get_grid(grid_id), flush=True)
        select(api, (0, 0, 0), (0, 4, 0))
        api.screenshot_save(str(OUT / "before.png"))
        press(api, "H")
        press(api, "Escape")
        api.screenshot_save(str(OUT / "hidden.png"))
        assert not aim(api, (0, 2, 0))["hit"], "Hidden armor still collides"
        assert aim(api, (2, 2, 0))["hit"], "Unselected armor lost collision"
        print("PASS armor cutaway preserves unselected collisions", flush=True)
        select(api, (4, 0, 0), (4, 4, 0))
        press(api, "H")
        assert not aim(api, (4, 2, 0))["hit"]
        assert not aim(api, (0, 2, 0))["hit"], "Second box replaced the first mask"
        press(api, "H", ["LeftShift"])
        press(api, "Escape")
        assert aim(api, (4, 2, 0))["hit"]
        assert not aim(api, (0, 2, 0))["hit"]
        print("PASS boxes accumulate and subtract independently", flush=True)
        # Fly through the first cutaway using character thrust rather than teleporting through it.
        aim(api, (0, 2, 0))
        goal = api.call([CallOp.grid_to_world(grid_id, (0, 2, -2))]).call(0)["world"]
        result = api.character_move_to(*goal, speed="fly", timeout=12, reach=0.6)
        assert result["reached"], result
        print("PASS character flies through hidden armor", flush=True)
        # Exercise both policies, reversing Ctrl when the configured default is on.
        excluding = ["LeftControl"] if INCLUDES else None
        including = None if INCLUDES else ["LeftControl"]
        select(api, (6, 0, -1), (6, 4, 1))
        press(api, "H", excluding)
        assert aim(api, (7, 2, 0))[
            "hit"
        ], "Exclusion policy included a partially enclosed refinery"
        press(api, "H", including)
        assert not aim(api, (7, 2, 0))[
            "hit"
        ], "Inclusion policy failed to include the whole refinery"
        press(api, "H", ["LeftShift", *(including or [])])
        press(api, "Escape")
        assert aim(api, (7, 2, 0))["hit"]
        print("PASS multi-cell bounds and Ctrl inversion", flush=True)
        select(api, (4, 0, 0), (5, 2, 0))
        press(api, "H")
        press(api, "Escape")
        light = api.get_block(grid_id, (5, 1, 0))
        assert light["isWorking"], light
        assert all(
            abs(a - b) < 0.0001 for a, b in zip(light["colorMask"], [0.55, 0.4, 0.2])
        ), "Cutaway tint changed the saved block color"
        assert not aim(api, (5, 0, 0))["hit"], "Hidden battery still collides"
        print("PASS hidden battery powers hidden light", flush=True)
        press(api, "H", ["LeftControl", "LeftShift"])
        assert aim(api, (0, 2, 0))["hit"]
        assert aim(api, (5, 0, 0))["hit"]
        print("PASS global all-visible reset", flush=True)
        api.screenshot_save(str(OUT / "restored.png"))
        # Build one box containing the whole ship, then restore it without any aim target.
        select(api, (-1, 0, -1), (8, 4, 2))
        press(api, "H", ["LeftControl"])
        press(api, "Escape")
        # Recovery must not require an aim target on the hidden ship.
        assert not aim(api, (0, 2, 0))["hit"]
        assert not aim(api, (7, 2, 0))["hit"]
        press(api, "H", ["LeftControl", "LeftShift"])
        assert aim(api, (0, 2, 0))["hit"]
        assert aim(api, (7, 2, 0))["hit"]
        print("PASS entirely hidden grid can be recovered without aiming", flush=True)
        # Use the actual copy/cut mouse handlers; their Ctrl behavior must match cutaways.
        copied_mask_check(api, grid_id)
        mouse_checks(api, grid_id)
        # Replacing one hidden cube uncovers it without revealing neighboring cells.
        select(api, (0, 0, 0), (0, 4, 0))
        press(api, "H")
        press(api, "Escape")
        api.character_grid_event(grid_id, (0, 0, 0), kind="raze")
        time.sleep(0.5)
        assert not api.call([CallOp.cube_exists(grid_id, (0, 0, 0))]).call(0)["exists"]
        api.character_teleport(ORIGIN[0], ORIGIN[1], ORIGIN[2] + 20)
        placed = api.character_build_block(grid_id, (0, 0, 0))
        assert placed["sent"], placed
        time.sleep(1)
        assert aim(api, (0, 0, 0))["hit"], "New block inherited the cutaway"
        assert not aim(api, (0, 2, 0))["hit"], "Placement cleared neighboring cells"
        print(
            "PASS newly placed blocks clear only their occupied mask cells", flush=True
        )

        api.close_grid(grid_id)
        (OUT / "result.txt").write_text("All cutaway integration checks passed.\n")


if __name__ == "__main__":
    main()
