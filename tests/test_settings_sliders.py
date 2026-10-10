"""Ctrl-click numeric-entry checks in the rendered headless client (1280x720)."""

import time

import test_auto_hide as settings
import test_cutaway as t


def wait_screen(api, screen_type):
    for _ in range(60):
        screen = api.get_focused_screen()
        if screen["type"] == screen_type and screen["state"] == "OPENED":
            return
        time.sleep(0.05)
    raise AssertionError(f"Expected opened {screen_type}, got {screen}")


def number(api, label):
    return float(settings.row(api, label)[2]["properties"]["text"])


def open_number(api, label):
    # Native Tab navigation also scrolls the target into view.
    for _ in range(100):
        slider = settings.row(api, label)[1]
        y = round((slider["topLeft"]["y"] + slider["size"]["y"] / 2) * 720)
        if 180 < y < 580:
            break
        api.key("Tab", hold_frames=1)
        time.sleep(0.08)
    else:
        raise AssertionError(f"Could not focus {label}")
    # The game uses a centered 4:3 safe rectangle for GUI coordinates.
    x = round(640 + (slider["topLeft"]["x"] + slider["size"]["x"] / 2 - 0.5) * 960)
    y = round((slider["topLeft"]["y"] + slider["size"]["y"] / 2) * 720)
    assert 165 < y < 600, f"Slider is outside the scroll viewport: {y}"
    # The raw-state endpoint's mouse x/y are deltas. Queue an absolute click
    # separately while Control remains held, so this exercises real Ctrl-click.
    api.set_input_state(keys=["LeftControl"], mode="override")
    time.sleep(0.1)
    try:
        api.click(x, y)
        wait_screen(api, "AmountDialog")
    finally:
        api.clear_input_state()


def main():
    t.OUT.mkdir(parents=True, exist_ok=True)
    with t.RemoteAPI(t.URL, username="admin", password="SpaceEngineers") as api:
        settings.open_settings(api)
        wait_screen(api, "SettingsScreen")
        for label, value, expected in [
            ("Hidden block opacity (%)", 23, 23),
            ("Hidden block saturation (%)", 42, 42),
            ("Auto-hide radius (m)", 8.37, 8.4),
            ("Size text scale", 1.23, 1.23),
            ("Text shadow offset", 3, 3),
        ]:
            original = number(api, label)
            open_number(api, label)
            assert (
                abs(float(settings.controls(api)[0]["properties"]["text"]) - original)
                < 0.001
            )
            if label == "Auto-hide radius (m)":
                api.control_click(name="IncreaseButton")
                assert (
                    abs(
                        float(settings.controls(api)[0]["properties"]["text"])
                        - original
                        - 0.1
                    )
                    < 0.001
                )
                api.control_click(name="DecreaseButton")
                assert (
                    abs(
                        float(settings.controls(api)[0]["properties"]["text"])
                        - original
                    )
                    < 0.001
                )
            api.control_set("AmountTextbox", str(value))
            api.control_click(text="OK")
            wait_screen(api, "SettingsScreen")
            assert abs(number(api, label) - expected) < 0.001
            open_number(api, label)
            api.control_set("AmountTextbox", "0")
            api.control_click(text="Cancel")
            wait_screen(api, "SettingsScreen")
            assert (
                abs(number(api, label) - expected) < 0.001
            ), "Cancel changed the value"
            api.control_set(settings.row(api, label)[1]["name"], original)
            print(
                f"PASS Ctrl-click entry, confirmation, and cancellation: {label}",
                flush=True,
            )
        api.screenshot_save(str(t.OUT / "slider-settings.png"))
        settings.close_settings(api)
        (t.OUT / "sliders.txt").write_text("Numeric slider entry checks passed.\n")


if __name__ == "__main__":
    main()
