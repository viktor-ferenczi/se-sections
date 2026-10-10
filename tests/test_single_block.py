"""Copy and cut of the highlighted block while choosing the first corner."""

import time

import test_auto_hide_building as b
import test_cutaway as t

CELL = (2, 2, 0)
NEIGHBORS = ((1, 2, 0), (3, 2, 0), (2, 1, 0), (2, 3, 0))


def highlight(api):
    target = b.world(api, CELL)
    b.look_from(api, (target[0], target[1], target[2] + 7), target)
    hit = api.get_character_target(15)
    assert hit["hit"] and tuple(hit["block"]["min"]) == CELL, hit
    t.press(api, "NumPad0")


def paste(api):
    """Pastes the clipboard far from the fixture; true if it is the one block."""
    before = {g["entityId"] for g in api.list_grids()}
    api.character_teleport(t.ORIGIN[0], t.ORIGIN[1], t.ORIGIN[2] + 100)
    api.character_look_at(t.ORIGIN[0], t.ORIGIN[1], t.ORIGIN[2] + 90)
    time.sleep(0.5)
    api.click(640, 360)
    time.sleep(1)
    copies = [g for g in api.list_grids() if g["entityId"] not in before]
    assert len(copies) == 1, copies
    # A copy keeps the cell coordinates of its source.
    fixture, t.GRID_ID = t.GRID_ID, copies[0]["entityId"]
    single = b.exists(api, CELL) and not any(b.exists(api, c) for c in NEIGHBORS)
    t.GRID_ID = fixture
    api.close_grid(copies[0]["entityId"])
    # A completed paste can keep the clipboard active for another paste.
    t.press(api, "Escape")
    if api.get_state()["paused"]:
        t.press(api, "Escape")
    return single


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
        api.character_teleport(t.ORIGIN[0], t.ORIGIN[1], t.ORIGIN[2] + 20)
        time.sleep(0.5)
        t.GRID_ID = api.paste_blueprint(
            xml=t.blueprint(), position=t.ORIGIN, forward=(0, 0, -1), up=(0, 1, 0)
        )[0]["entityId"]
        time.sleep(1)

        highlight(api)
        api.screenshot_save(str(t.OUT / "single-block-hints.png"))
        t.press(api, "Insert")
        assert paste(api), "Insert did not copy exactly the highlighted block"
        assert b.exists(api, CELL), "Copy removed the block"
        print("PASS Insert copies the highlighted block", flush=True)

        highlight(api)
        t.press(api, "Delete")
        screen = api.get_focused_screen()
        assert "MessageBox" in screen["type"], screen["type"]
        assert b.exists(api, CELL), "Cut did not wait for the confirmation"
        api.control_click(text="Yes")
        time.sleep(0.5)
        assert not b.exists(api, CELL), "Delete did not cut the highlighted block"
        for cell in NEIGHBORS:
            assert b.exists(api, cell), f"Cut removed the neighbor {cell}"
        assert paste(api), "Cut did not put exactly one block on the clipboard"
        print("PASS Delete cuts the highlighted block after confirmation", flush=True)

        api.close_grid(t.GRID_ID)
        (t.OUT / "single-block.txt").write_text("Single block copy/cut passed.\n")


if __name__ == "__main__":
    main()
