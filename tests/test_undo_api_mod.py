"""Undo's API from a mod script (SE-606): the probe mod in Undo's tests renames a
grid on a chat command and adds the rename to the history as a step it applies
itself (AddStep, RegisterStepHandler). The mod compiles under the game's mod
whitelist, so this is also the check that mods can use the API at all.

SECTIONS_SLOT=<n> uv run pytest tests/test_undo_api_mod.py
"""

import time

import rig
import undo_steps as u

UNDO = True
MODS = [rig.UNDO_REPO / "tests" / "data" / "UndoApiProbe"]


def name(game) -> str:
    grid = game.api.get_grid(game.grid)
    for key in ("name", "displayName", "customName"):
        if key in grid:
            return grid[key]
    raise AssertionError(f"No name in {sorted(grid)}")


def test_mod_step(game):
    history = u.History(rig.client(0).appdata / "Undo" / "status.json")
    old = name(game)

    game.api.send_chat(f"/probe {game.grid} Probe renamed")
    u.wait_until(lambda: name(game) == "Probe renamed", "the rename")
    node = u.wait_until(
        lambda: (n := history.current())
        and n["label"] == "renamed with the probe mod"
        and n,
        f"the mod's step in the history, which has {history.labels()}",
    )

    u.undo(game, history, node)
    u.wait_until(lambda: name(game) == old, "the old name back")
    u.redo(game, history, node)
    u.wait_until(lambda: name(game) == "Probe renamed", "the rename again")

    # The step is saved with the world, and the mod registers its handler again in
    # the new session
    path = game.api.get_state()["path"]
    game.save()
    try:
        game.api.load(path)
    except Exception:  # noqa: BLE001 -- the load outlives the HTTP timeout
        pass
    # The old session stays ready until the loading screen takes it down
    time.sleep(10)
    rig.wait_world(game.api)
    rig.ensure_character(game.api)
    rig.focus_gameplay(game.api)
    node = u.wait_until(history.current, "the history loaded")
    assert node["label"] == "renamed with the probe mod", history.labels()
    u.undo(game, history, node)
    u.wait_until(lambda: name(game) == old, "the old name back after the reload")
