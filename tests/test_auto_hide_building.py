"""Building and removing blocks through auto-hidden blocks from inside a ship."""

import time

import test_cutaway as t

ARMOR = "MyObjectBuilder_CubeBlock/LargeBlockArmorBlock"
# A spine along Z carrying a second row with a two-cell gap. From inside the
# near end of that row, the far end lies beyond the default 7.5 m sphere.
SPINE = [(0, 0, z) for z in range(6)]
ROW = [(1, 0, 0), (1, 0, 1), (1, 0, 4), (1, 0, 5)]
INSIDE, HIDDEN, GAP, TARGET = (1, 0, 0), (1, 0, 1), (1, 0, 3), (1, 0, 4)


def blueprint():
    # The shared fixture's envelope around this test's own blocks
    xml = t.blueprint()
    start = xml.index("<MyObjectBuilder_CubeBlock ")
    end = xml.index("</CubeBlocks>")
    return xml[:start] + "".join(t.block(cell) for cell in SPINE + ROW) + xml[end:]


def world(api, cell):
    return api.call([t.CallOp.grid_to_world(t.GRID_ID, cell)]).call(0)["world"]


def exists(api, cell):
    return api.call([t.CallOp.cube_exists(t.GRID_ID, cell)]).call(0)["exists"]


def look_from(api, eye, target):
    # A flying character keeps whatever roll it has, so place the feet below
    # the head along its own up vector. Turning changes that vector; repeat.
    for _ in range(3):
        up = api.get_character()["up"]
        api.character_teleport(*(e - 1.6 * u for e, u in zip(eye, up)))
        time.sleep(0.3)
        api.character_look_at(*target)
        time.sleep(0.3)


def mouse(api, button):
    # The GUI click endpoint does not reach the cube builder.
    api.set_input_state(mode="override", **{f"mouse_{button}": True})
    time.sleep(0.5)
    api.clear_input_state()
    time.sleep(1)


def main():
    t.OUT.mkdir(parents=True, exist_ok=True)
    with t.RemoteAPI(
        t.URL,
        username="admin",
        password="SpaceEngineers",
    ) as api:
        assert api.get_state()["active"]
        if api.get_character().get("controlledEntity"):
            api.character_use()
        if not api.get_character()["jetpack"]:
            t.press(api, "X")
        api.character_set_dampeners(True)
        for _ in range(30):
            if api.get_view()["localSpeed"] < 0.1:
                break
            time.sleep(0.2)
        api.character_teleport(t.ORIGIN[0], t.ORIGIN[1], t.ORIGIN[2] - 20)
        time.sleep(0.5)
        t.GRID_ID = api.paste_blueprint(
            xml=blueprint(), position=t.ORIGIN, forward=(0, 0, -1), up=(0, 1, 0)
        )[0]["entityId"]
        time.sleep(1)
        inside, target = world(api, INSIDE), world(api, TARGET)
        # Start in front of the row, then fly into its first block with auto-hide on.
        outside = (inside[0], inside[1], inside[2] - 5)
        look_from(api, outside, target)
        assert api.get_character_target(12)["hit"], "The row should start solid"
        t.press(api, "OemPipe", ["LeftControl", "LeftAlt"])
        assert not api.get_character_target(12)["hit"], "Auto-hide did not start"
        result = api.character_move_to(*inside, speed="fly", timeout=12, reach=1.0)
        assert result["reached"], result
        time.sleep(1)
        api.set_toolbar_slot(0, ARMOR)
        api.key("D1")
        time.sleep(1)
        look_from(api, inside, target)
        api.screenshot_save(str(t.OUT / "auto-hide-building.png"))

        mouse(api, "left")
        assert exists(api, GAP), "Block was not built on the visible block's face"
        assert not exists(api, (1, 0, 2)), "Block was built on a hidden block instead"
        print("PASS building through hidden blocks from inside the ship", flush=True)

        # The new block is inside the sphere, so it is hidden as well by now.
        look_from(api, inside, target)
        mouse(api, "right")
        assert not exists(api, TARGET), "The visible block was not removed"
        for cell in (INSIDE, HIDDEN, GAP):
            assert exists(api, cell), f"Hidden block {cell} was removed"
        print("PASS removing through hidden blocks from inside the ship", flush=True)

        api.key("D0")
        # Auto-hide refuses to turn off around the character.
        api.character_teleport(inside[0], inside[1] - 1.5, inside[2] - 20)
        time.sleep(0.5)
        t.press(api, "H", ["LeftControl", "LeftShift"])
        api.close_grid(t.GRID_ID)
        (t.OUT / "auto-hide-building.txt").write_text(
            "Auto-hide build and remove checks passed.\n"
        )


if __name__ == "__main__":
    main()
