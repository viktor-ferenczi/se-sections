"""Selection keys stay reserved even when their modifiers do not match."""

import time

import test_cutaway as t


def main():
    with t.RemoteAPI(
        "http://127.0.0.1:24188", username="admin", password="SpaceEngineers"
    ) as api:
        assert api.get_state()["active"]
        if api.get_character().get("controlledEntity"):
            api.character_use()
            time.sleep(1)
        if not api.get_character()["jetpack"]:
            t.press(api, "X")
        api.character_set_dampeners(True)
        t.GRID_ID = api.paste_blueprint(
            xml=t.blueprint(), position=t.ORIGIN, forward=(0, 0, -1), up=(0, 1, 0)
        )[0]["entityId"]
        time.sleep(1)
        t.select(api, (0, 0, 0), (4, 4, 0))
        for modifiers in (["LeftShift"], ["LeftControl", "LeftShift"]):
            api.key("Enter", modifiers, hold_frames=20)
            time.sleep(0.4)
            assert "Chat" not in api.get_focused_screen()["type"], (
                "Reserved Enter opened chat instead of remaining in box selection",
                modifiers,
            )
        print("PASS mismatched modifiers and held keys stay reserved")
        before = api.get_character()["position"]
        api.key("D", hold_frames=30)
        time.sleep(0.6)
        after = api.get_character()["position"]
        assert sum((a - b) ** 2 for a, b in zip(after, before)) > 0.01
        print("PASS movement remains available with the yellow box active")
        t.press(api, "Escape")
        t.press(api, "Enter", ["LeftControl", "LeftShift"])
        assert (
            "Chat" in api.get_focused_screen()["type"]
        ), "Leaving selection did not restore the original Enter action"
        t.press(api, "Escape")
        print("PASS leaving selection restores normal key handling")
        api.close_grid(t.GRID_ID)


if __name__ == "__main__":
    main()
