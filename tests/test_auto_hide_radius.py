"""Hotkeys adjust the active radius without changing the configured default."""

import re
import time

import test_auto_hide as settings
import test_cutaway as t


def main():
    with t.RemoteAPI(t.URL, username="admin", password="SpaceEngineers") as api:
        if api.get_character().get("controlledEntity"):
            api.character_use()
            time.sleep(1)
        if not api.get_character()["jetpack"]:
            t.press(api, "X")
        api.character_set_dampeners(True)
        api.character_teleport(t.ORIGIN[0] + 8.8, t.ORIGIN[1], t.ORIGIN[2])
        xml = re.sub(
            r"<CubeBlocks>.*?</CubeBlocks>",
            "<CubeBlocks>"
            + t.block((0, 0, 0))
            + t.block((0, -1, 0))
            + t.block((0, -3, 0), "BatteryBlock", "LargeBlockBatteryBlock")
            + "</CubeBlocks>",
            t.blueprint(),
        )
        t.GRID_ID = api.paste_blueprint(
            xml=xml, position=t.ORIGIN, forward=(0, 0, -1), up=(0, 1, 0)
        )[0]["entityId"]
        time.sleep(1)
        target = api.call([t.CallOp.grid_to_world(t.GRID_ID, (0, 0, 0))]).call(0)[
            "world"
        ]
        # The character is 7.55 m beyond the cube's nearest face.
        api.character_teleport(target[0] + 8.8, target[1], target[2])
        api.character_look_at(*target)
        api.character_teleport(target[0] + 8.8, target[1], target[2])
        time.sleep(0.5)
        settings.open_settings(api)
        settings.set_radius(api, 7.5)
        api.control_set(settings.row(api, "Auto-hide blocks")[1]["name"], True)
        settings.close_settings(api)
        assert api.get_character_target(20)["hit"]
        t.press(api, "OemCloseBrackets", ["LeftControl", "LeftAlt"])
        assert not api.get_character_target(20)[
            "hit"
        ], "8.0 m radius did not hide the block"
        settings.open_settings(api)
        assert (
            float(settings.row(api, "Auto-hide radius (m)")[2]["properties"]["text"])
            == 7.5
        )
        settings.close_settings(api)
        assert not api.get_character_target(20)[
            "hit"
        ], "Active radius did not survive config inspection"
        print(
            "PASS radius hotkey changes collision without changing the configured default"
        )
        t.press(api, "OemPipe", ["LeftControl", "LeftAlt"])
        t.press(api, "OemPipe", ["LeftControl", "LeftAlt"])
        assert api.get_character_target(20)[
            "hit"
        ], "Enabling did not reload the 7.5 m default"
        t.press(api, "OemCloseBrackets", ["LeftControl", "LeftAlt"])
        assert not api.get_character_target(20)["hit"]
        t.press(api, "OemOpenBrackets", ["LeftControl", "LeftAlt"])
        assert api.get_character_target(20)["hit"]
        print(
            "PASS disabling/re-enabling resets the radius and decrease uses 0.5 m steps"
        )
        settings.open_settings(api)
        settings.set_radius(api, 8)
        settings.close_settings(api)
        assert api.get_character_target(20)[
            "hit"
        ], "Changing the default changed the active radius"
        t.press(api, "OemPipe", ["LeftControl", "LeftAlt"])
        t.press(api, "OemPipe", ["LeftControl", "LeftAlt"])
        assert not api.get_character_target(20)[
            "hit"
        ], "Next enable did not load the new default"
        t.press(api, "OemPipe", ["LeftControl", "LeftAlt"])
        settings.open_settings(api)
        settings.set_radius(api, 7.5)
        settings.close_settings(api)
        api.close_grid(t.GRID_ID)
        print("PASS config radius takes effect only on the next enable")


if __name__ == "__main__":
    main()
