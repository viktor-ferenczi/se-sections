"""Save/reload checks; run only against a disposable creative world."""

import os
import time

import test_cutaway as t


def main() -> None:
    t.OUT.mkdir(parents=True, exist_ok=True)
    with t.RemoteAPI(
        os.environ.get("SE_REMOTE_URL", "http://127.0.0.1:24188"),
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
        else:
            raise AssertionError("Character did not stop")
        api.character_teleport(t.ORIGIN[0], t.ORIGIN[1], t.ORIGIN[2] + 20)
        time.sleep(0.5)
        t.GRID_ID = api.paste_blueprint(
            xml=t.blueprint(), position=t.ORIGIN, forward=(0, 0, -1), up=(0, 1, 0)
        )[0]["entityId"]
        time.sleep(1)
        t.select(api, (0, 0, 0), (0, 4, 0))
        t.press(api, "H")
        assert not t.aim(api, (0, 2, 0))["hit"]
        t.press(api, "J", ["LeftControl", "LeftShift"])
        assert t.aim(api, (0, 2, 0))["hit"]
        print("PASS Ctrl+Shift+J restores all grids", flush=True)
        t.select(api, (0, 0, 0), (0, 4, 0))
        t.press(api, "H")
        t.press(api, "Escape")
        assert not t.aim(api, (0, 2, 0))["hit"]
        api.screenshot_save(str(t.OUT / "ghosts.png"))
        t.press(api, "OemPipe", ["LeftControl", "LeftAlt"])
        api.save()
        time.sleep(0.5)
        for _ in range(60):
            if not api.get_state()["saving"]:
                break
            time.sleep(0.5)
        else:
            raise AssertionError("Save did not finish")
        frame_before = api.get_state()["frameCounter"]
        api.reload(save=False)
        for _ in range(60):
            time.sleep(0.5)
            state = api.get_state()
            if state["active"] and state["frameCounter"] < frame_before:
                break
        else:
            raise AssertionError("Reload did not finish")
        time.sleep(1)
        assert t.aim(api, (0, 2, 0))["hit"], "Reload persisted hidden collision"
        light = api.get_block(t.GRID_ID, (5, 1, 0))
        assert all(
            abs(a - b) < 0.0001 for a, b in zip(light["colorMask"], [0.55, 0.4, 0.2])
        )
        api.screenshot_save(str(t.OUT / "reloaded.png"))
        print(
            "PASS save/reload clears masks, disables auto-hide, and preserves block colors",
            flush=True,
        )
        api.close_grid(t.GRID_ID)
        (t.OUT / "lifecycle.txt").write_text(
            "Shortcut and save/reload checks passed.\n"
        )


if __name__ == "__main__":
    main()
