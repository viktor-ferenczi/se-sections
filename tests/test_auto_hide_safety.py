"""Auto-hide shutdown must not restore collision through the character."""

import time

import test_auto_hide as settings
import test_cutaway as t


def enabled(api):
    settings.open_settings(api)
    value = settings.row(api, "Auto-hide blocks")[1]["properties"]["isChecked"]
    settings.close_settings(api)
    time.sleep(0.8)
    return value


def main():
    t.OUT.mkdir(parents=True, exist_ok=True)
    with t.RemoteAPI(t.URL, username="admin", password="SpaceEngineers") as api:
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
        t.GRID_ID = api.paste_blueprint(
            xml=t.blueprint(), position=t.ORIGIN, forward=(0, 0, -1), up=(0, 1, 0)
        )[0]["entityId"]
        time.sleep(1)
        t.aim(api, (0, 2, 0))
        t.press(api, "OemPipe", ["LeftControl", "LeftAlt"])
        assert enabled(api)
        target = api.call([t.CallOp.grid_to_world(t.GRID_ID, (0, 2, 0))]).call(0)[
            "world"
        ]
        api.character_teleport(target[0], target[1] - 0.5, target[2])
        time.sleep(0.5)
        t.press(api, "OemPipe", ["LeftControl", "LeftAlt"])
        assert enabled(api), "Shutdown restored collision around the character"
        t.press(api, "Enter")
        api.screenshot_save(str(t.OUT / "refusal-message.png"))
        t.press(api, "Escape")
        print(
            "PASS toggle refuses shutdown inside a hidden block and shows a message",
            flush=True,
        )
        settings.open_settings(api)
        api.control_set(settings.row(api, "Auto-hide blocks")[1]["name"], False)
        assert settings.row(api, "Auto-hide blocks")[1]["properties"]["isChecked"]
        api.control_click(text="Show all blocks on all grids")
        time.sleep(0.3)
        assert settings.row(api, "Auto-hide blocks")[1]["properties"]["isChecked"]
        settings.close_settings(api)
        t.press(api, "H", ["LeftControl", "LeftShift"])
        assert enabled(api), "Global recovery bypassed shutdown protection"
        print(
            "PASS config checkbox, reset button, and global recovery respect the guard",
            flush=True,
        )
        # The character's origin is outside the cube (half-size 1.25 m),
        # but the body still intersects its boundary.
        api.character_teleport(target[0] - 1.3, target[1] - 0.5, target[2])
        time.sleep(0.5)
        t.press(api, "OemPipe", ["LeftControl", "LeftAlt"])
        assert enabled(api), "Partial body overlap was missed"
        print("PASS partial body overlap refuses shutdown", flush=True)
        # Leave ample clearance; nearby blocks can stay ghosted until shutdown.
        t.aim(api, (0, 2, 0))
        t.press(api, "OemPipe", ["LeftControl", "LeftAlt"])
        assert not enabled(api)
        assert t.aim(api, (0, 2, 0))["hit"]
        print("PASS moving clear permits shutdown and restores collision", flush=True)
        t.press(api, "OemPipe", ["LeftControl", "LeftAlt"])
        api.character_teleport(target[0], target[1] - 0.5, target[2])
        time.sleep(0.5)
        frame = api.get_state()["frameCounter"]
        api.reload(save=False)
        for _ in range(60):
            time.sleep(0.5)
            state = api.get_state()
            if state["active"] and state["frameCounter"] < frame:
                break
        else:
            raise AssertionError("Reload did not finish")
        time.sleep(1)
        assert not enabled(api), "Unload did not force automatic hiding off"
        print("PASS world reload bypasses the guard for cleanup", flush=True)
        (t.OUT / "safety.txt").write_text("Auto-hide shutdown safety checks passed.\n")


if __name__ == "__main__":
    main()
