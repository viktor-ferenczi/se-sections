"""Cutaway shortcuts do not fall through to HUD controls on repeated presses."""

import time

import test_cutaway as t
from test_auto_hide_safety import enabled


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
        cursor = api.get_hud_notifications()["latest"]
        t.press(api, "H")
        assert any(
            "Signals switched" in item["text"]
            for item in api.get_hud_notifications(after=cursor)["notifications"]
        ), "Baseline H did not change the HUD signal mode"
        cursor = api.get_hud_notifications()["latest"]
        t.press(api, "NumPad0")
        t.press(api, "H")
        t.press(api, "H")
        assert not any(
            "Signals switched" in item["text"]
            for item in api.get_hud_notifications(after=cursor)["notifications"]
        ), "H fell through while choosing the first corner"
        t.press(api, "Escape")
        t.select(api, (0, 0, 0), (4, 4, 0))
        cursor = api.get_hud_notifications()["latest"]
        t.press(api, "H")
        t.press(api, "H")
        t.press(api, "H")
        assert not any(
            "Signals switched" in item["text"]
            for item in api.get_hud_notifications(after=cursor)["notifications"]
        ), "Repeated H presses changed the HUD signal mode"
        t.press(api, "H", ["LeftShift"])
        t.press(api, "H", ["LeftShift"])
        assert not any(
            "Signals switched" in item["text"]
            for item in api.get_hud_notifications(after=cursor)["notifications"]
        ), "Repeated show presses changed the HUD signal mode"
        print(
            "PASS first-corner and repeated hide/show presses leave HUD signals unchanged"
        )
        before = api.get_character()["position"]
        api.key("D", hold_frames=30)
        time.sleep(0.6)
        after = api.get_character()["position"]
        assert sum((a - b) ** 2 for a, b in zip(after, before)) > 0.01
        print("PASS movement remains available with the yellow box active")
        t.press(api, "Escape")
        cursor = api.get_hud_notifications()["latest"]
        t.press(api, "H")
        assert any(
            "Signals switched" in item["text"]
            for item in api.get_hud_notifications(after=cursor)["notifications"]
        ), "Leaving selection did not restore the HUD signal control"
        t.press(api, "Enter", ["LeftControl", "LeftShift"])
        assert (
            "Chat" in api.get_focused_screen()["type"]
        ), "Leaving selection did not restore the original Enter action"
        t.press(api, "Escape")
        print("PASS leaving selection restores normal key handling")
        t.select(api, (0, 0, 0), (4, 4, 0))
        t.press(api, "H")
        t.press(api, "Escape")
        assert not t.aim(api, (0, 2, 0))["hit"]
        t.press(api, "OemPipe", ["LeftControl", "LeftAlt"])
        assert enabled(api)
        t.press(api, "H", ["LeftControl", "LeftShift"])
        assert not enabled(api), "Ctrl+Shift+H did not stop auto-hide"
        assert t.aim(api, (0, 2, 0))[
            "hit"
        ], "Ctrl+Shift+H did not restore manual cutaways"
        print(
            "PASS Ctrl+Shift+H restores cutaways and stops auto-hide while outside blocks"
        )
        api.close_grid(t.GRID_ID)


if __name__ == "__main__":
    main()
