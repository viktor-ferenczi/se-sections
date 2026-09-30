"""Auto-hide and native config dialog checks in a disposable creative world."""

import time

import test_cutaway as t


def controls(api):
    def flatten(items):
        for item in items:
            yield item
            yield from flatten(item.get("children", []))

    return list(flatten(api.get_focused_screen()["controls"]))


def row(api, label):
    items = controls(api)
    index = next(
        i for i, c in enumerate(items) if c.get("properties", {}).get("text") == label
    )
    return items[index : index + 5]


def open_settings(api):
    t.press(api, "OemQuestion", ["LeftControl", "LeftAlt"])
    screen = api.get_focused_screen()
    assert screen["type"] == "ConfigurePlugin", screen["type"]
    table = next(c for c in controls(api) if c["type"] == "MyGuiControlTable")
    assert (
        table["properties"]["rowsCount"] == 2
    ), "Use the Remote + Sections test profile"
    api.control_set(table["name"], 1)
    t.press(api, "Enter")
    assert api.get_focused_screen()["type"] == "SettingsScreen"


def close_settings(api):
    t.press(api, "Escape")
    t.press(api, "Escape")
    if api.get_state().get("paused"):
        t.press(api, "Escape")


def set_radius(api, value, expected=None):
    api.control_set(row(api, "Auto-hide radius (m)")[1]["name"], value)
    actual = float(row(api, "Auto-hide radius (m)")[2]["properties"]["text"])
    assert abs(actual - (value if expected is None else expected)) < 0.001, actual


def remap(api, label, key):
    api.control_click(name=row(api, label)[1]["name"])
    assert "AssignKey" in api.get_focused_screen()["type"]
    api.key(key, ["LeftControl", "LeftAlt"], hold_frames=16)
    time.sleep(0.8)
    assert (
        api.get_focused_screen()["type"] == "SettingsScreen"
    ), api.get_focused_screen()["type"]


def aim_far(api, cell):
    target = api.call([t.CallOp.grid_to_world(t.GRID_ID, cell)]).call(0)["world"]
    api.character_teleport(target[0], target[1] - 1.5, target[2] + 12)
    time.sleep(0.3)
    api.character_look_at(*target)
    time.sleep(0.2)
    return api.get_character_target(20)


def main():
    t.OUT.mkdir(parents=True, exist_ok=True)
    with t.RemoteAPI(
        "http://127.0.0.1:24188", username="admin", password="SpaceEngineers"
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
        api.character_teleport(t.ORIGIN[0], t.ORIGIN[1], t.ORIGIN[2] + 20)
        time.sleep(0.5)
        t.GRID_ID = api.paste_blueprint(
            xml=t.blueprint(), position=t.ORIGIN, forward=(0, 0, -1), up=(0, 1, 0)
        )[0]["entityId"]
        time.sleep(1)
        open_settings(api)
        assert not row(api, "Auto-hide blocks")[1]["properties"]["isChecked"]
        for value, expected in [(0, 0), (50, 50), (8.37, 8.4), (7.5, 7.5)]:
            set_radius(api, value, expected)
        for label, key in [
            ("Toggle auto hide", "F7"),
            ("Decrease auto hide radius", "F9"),
            ("Increase auto hide radius", "F8"),
        ]:
            binding = row(api, label)
            assert binding[2]["properties"]["isChecked"]
            assert binding[3]["properties"]["isChecked"]
            assert not binding[4]["properties"]["isChecked"]
            remap(api, label, key)
        api.screenshot_save(str(t.OUT / "auto-hide-settings.png"))
        close_settings(api)
        t.press(api, "F8", ["LeftControl", "LeftAlt"])
        open_settings(api)
        assert float(row(api, "Auto-hide radius (m)")[2]["properties"]["text"]) == 7.6
        close_settings(api)
        t.press(api, "F9", ["LeftControl", "LeftAlt"])
        t.press(api, "F7", ["LeftControl", "LeftAlt"])
        assert not t.aim(api, (0, 2, 0))[
            "hit"
        ], "Rebound toggle did not enable auto-hide"
        t.press(api, "F7", ["LeftControl", "LeftAlt"])
        assert t.aim(api, (0, 2, 0))["hit"]
        print(
            "PASS config slider range/rounding and all three rebound shortcuts",
            flush=True,
        )
        open_settings(api)
        assert float(row(api, "Auto-hide radius (m)")[2]["properties"]["text"]) == 7.5
        for label, key in [
            ("Toggle auto hide", "OemPipe"),
            ("Decrease auto hide radius", "OemOpenBrackets"),
            ("Increase auto hide radius", "OemCloseBrackets"),
        ]:
            remap(api, label, key)
        api.control_set(row(api, "Include intersecting blocks")[1]["name"], False)
        api.control_set(row(api, "Hidden block opacity (%)")[1]["name"], 10)
        api.control_set(row(api, "Hidden block saturation (%)")[1]["name"], 100)
        close_settings(api)
        t.select(api, (1, 0, 0), (1, 4, 0))
        t.press(api, "H")
        t.press(api, "Escape")
        t.press(api, "OemPipe", ["LeftControl", "LeftAlt"])
        assert not t.aim(api, (0, 2, 0))["hit"]
        assert aim_far(api, (0, 2, 0))["hit"], "Moving away did not restore collision"
        assert not aim_far(api, (1, 2, 0))["hit"], "Auto-hide changed the manual mask"
        t.press(api, "OemPipe", ["LeftControl", "LeftAlt"])
        assert t.aim(api, (0, 2, 0))["hit"]
        assert not t.aim(api, (1, 2, 0))["hit"]
        print(
            "PASS sphere follows character and preserves manual mask on toggle-off",
            flush=True,
        )
        t.press(api, "OemPipe", ["LeftControl", "LeftAlt"])
        open_settings(api)
        set_radius(api, 0)
        close_settings(api)
        assert t.aim(api, (0, 2, 0))["hit"]
        open_settings(api)
        set_radius(api, 50)
        close_settings(api)
        assert not aim_far(api, (0, 2, 0))["hit"]
        open_settings(api)
        set_radius(api, 7.5)
        close_settings(api)
        t.press(api, "OemCloseBrackets", ["LeftControl", "LeftAlt"])
        open_settings(api)
        assert float(row(api, "Auto-hide radius (m)")[2]["properties"]["text"]) == 7.6
        close_settings(api)
        t.press(api, "OemOpenBrackets", ["LeftControl", "LeftAlt"])
        open_settings(api)
        assert float(row(api, "Auto-hide radius (m)")[2]["properties"]["text"]) == 7.5
        assert row(api, "Auto-hide blocks")[1]["properties"]["isChecked"]
        api.control_click(text="Show all blocks on all grids")
        time.sleep(0.3)
        assert not row(api, "Auto-hide blocks")[1]["properties"]["isChecked"]
        close_settings(api)
        assert t.aim(api, (0, 2, 0))["hit"]
        assert t.aim(api, (1, 2, 0))["hit"]
        print(
            "PASS radius endpoints, default shortcuts, and config reset button",
            flush=True,
        )
        api.close_grid(t.GRID_ID)
        (t.OUT / "auto-hide.txt").write_text(
            "Auto-hide and config dialog checks passed.\n"
        )


if __name__ == "__main__":
    main()
