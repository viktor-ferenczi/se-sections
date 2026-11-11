"""Sections with the Undo plugin (SE-606): what a cut or a delete with Sections
leaves in Undo's history, and that Ctrl-Z and Ctrl-Y take it back and do it again.
The same steps run offline, on a dedicated server, on a lobby host and on a joined
client; only where Undo's history is read from differs.

The oracle is the world: the blocks exist or not (Remote's cube_exists), and the
block references read from the saved world are intact after an undo, which shows
that the blocks came back as themselves, with their entity ids.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import harness as h
from se_remote import OpError
from harness import EXPECTED, OWNERS, OWNER_ROW, TARGET_ROW, TARGETS

TARGET_CELLS = [pos for pos, _, _ in TARGETS.values()]
OWNER_CELLS = [pos for pos, _, _ in OWNERS.values()]


def wait_until(predicate, what: str, timeout: float = 60.0):
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:
            return value
        assert time.monotonic() < deadline, f"Timed out waiting for {what}"
        time.sleep(0.5)


class History:
    """One player's build history, from Undo's debug status file: status.json of
    the local player, or status-players.json of the players a server serves"""

    def __init__(self, path: Path, steam_id: int | None = None):
        self.path = path
        self.steam_id = steam_id

    def build(self) -> dict:
        for _ in range(20):
            try:
                status = json.loads(self.path.read_text(encoding="utf-8"))
                break
            except FileNotFoundError:
                return {"nodes": [], "current": 0}
            except ValueError:  # written while read
                time.sleep(0.1)
        else:
            raise AssertionError(f"{self.path} is not readable")
        if self.steam_id is not None:
            status = status.get("players", {}).get(str(self.steam_id)) or {}
        return (status.get("histories") or {}).get("build") or {
            "nodes": [],
            "current": 0,
        }

    def node(self, node_id: int) -> dict | None:
        return next((n for n in self.build()["nodes"] if n["id"] == node_id), None)

    def current(self) -> dict | None:
        return self.node(self.build()["current"])

    def labels(self) -> list[str]:
        return [n["label"] for n in self.build()["nodes"]]


def exists(game: h.Game, cell) -> bool:
    """False while the grid is unknown: undoing a removal that took a rotor apart
    closes the grid and creates it again, which reaches a client in two steps"""
    try:
        return game.exists(cell)
    except OpError:
        return False


def exist(game: h.Game, cells) -> bool:
    return all(exists(game, c) for c in cells)


def gone(game: h.Game, cells) -> bool:
    return not any(exists(game, c) for c in cells)


def wait_recorded(history: History, verb: str, count: int) -> dict:
    label = f"{verb} {count} blocks with Sections"
    return wait_until(
        lambda: (n := history.current()) and n["label"].startswith(label) and n,
        f'"{label}" in the history, which has {history.labels()}',
    )


def undo(game: h.Game, history: History, node: dict) -> None:
    game.press("Z", ["LeftControl"])
    wait_until(
        lambda: history.build()["current"] == node["parent"],
        f"the undo of {node['label']}",
    )


def redo(game: h.Game, history: History, node: dict) -> None:
    game.press("Y", ["LeftControl"])
    wait_until(
        lambda: history.build()["current"] == node["id"],
        f"the redo of {node['label']}",
    )


def assert_references(game: h.Game) -> None:
    refs = h.references(game.saved_grids().values())
    assert refs == EXPECTED, h.broken(refs)


def cut_undo_redo(game: h.Game, history: History) -> None:
    """A cut of the target row, with the rotor stators (Ctrl): undo puts the whole
    grid back as it was, since rotor stators hold subgrids"""
    game.cut(*TARGET_ROW, ctrl=True)
    game.leave_screens()
    wait_until(lambda: gone(game, TARGET_CELLS), "the cut")
    node = wait_recorded(history, "cut", len(TARGET_CELLS))

    undo(game, history, node)
    wait_until(lambda: exist(game, TARGET_CELLS), "the blocks back after the undo")
    assert_references(game)

    redo(game, history, node)
    wait_until(lambda: gone(game, TARGET_CELLS), "the cut again after the redo")

    undo(game, history, node)
    wait_until(lambda: exist(game, TARGET_CELLS), "the blocks back after undo")
    assert_references(game)


def delete_undo_redo(game: h.Game, history: History) -> None:
    """A delete of the owner row, plain blocks: undo restores each block with its
    toolbar and references"""
    game.delete(*OWNER_ROW)
    game.leave_screens()
    wait_until(lambda: gone(game, OWNER_CELLS), "the delete")
    node = wait_recorded(history, "deleted", len(OWNER_CELLS))

    undo(game, history, node)
    wait_until(lambda: exist(game, OWNER_CELLS), "the blocks back after the undo")
    assert_references(game)

    redo(game, history, node)
    wait_until(lambda: gone(game, OWNER_CELLS), "the delete again after the redo")

    undo(game, history, node)
    wait_until(lambda: exist(game, OWNER_CELLS), "the blocks back after undo")
    assert_references(game)


def cut_paste_back_undo(game: h.Game, history: History) -> None:
    """Cut, paste back onto the grid: two steps, undone in turn"""
    game.cut(*TARGET_ROW, ctrl=True)
    wait_until(lambda: gone(game, TARGET_CELLS), "the cut")
    cut = wait_recorded(history, "cut", len(TARGET_CELLS))
    game.paste_on((15, 0, 0))
    wait_until(lambda: exist(game, TARGET_CELLS), "the paste back")
    paste = wait_until(
        lambda: (n := history.current()) and n["id"] != cut["id"] and n,
        "the paste in the history",
    )
    assert paste["parent"] == cut["id"], history.labels()

    undo(game, history, paste)
    wait_until(lambda: gone(game, TARGET_CELLS), "the paste undone")
    undo(game, history, cut)
    wait_until(lambda: exist(game, TARGET_CELLS), "the cut undone")
    assert_references(game)


ROTOR = (4, 1, -1)


def cut_rotor_with_head(game: h.Game, history: History) -> None:
    """A rotor base with its head: Sections cuts the base and closes the head's
    grid, which nothing holds any more. Undo puts both back, the head's grid with
    its own entity id."""
    grids = lambda: {g["entityId"] for g in game.api.list_grids()}  # noqa: E731
    known = grids()
    sent = game.api.character_build_block(game.grid, ROTOR, subtype="LargeStator")
    assert sent["sent"], sent
    (head,) = wait_until(lambda: grids() - known, "the rotor head's grid")

    game.cut_block(ROTOR, side=(0, 0, -1))
    game.leave_screens()
    wait_until(
        lambda: not exists(game, ROTOR) and head not in grids(),
        "the rotor and head cut",
    )
    node = wait_until(
        lambda: (n := history.current())
        and n["label"].startswith("cut 1 block with Sections, 1 subgrid")
        and n,
        f"the cut in the history, which has {history.labels()}",
    )

    undo(game, history, node)
    wait_until(
        lambda: exists(game, ROTOR) and head in grids(), "the rotor and head back"
    )
    redo(game, history, node)
    wait_until(lambda: not exists(game, ROTOR) and head not in grids(), "the cut again")
    undo(game, history, node)
    wait_until(
        lambda: exists(game, ROTOR) and head in grids(), "the rotor and head back"
    )


# --- symmetry (SE-1359) ---------------------------------------------------------------

# Plane setups on the fixture grid, each crossing the selected row at `mid`, the
# middle cell of the row along x: one plane even and odd, two odd planes, and
# three even planes, the y plane through the rows themselves
PLANE_SETUPS = {
    "none": lambda mid: {},
    "x-even": lambda mid: {"x": (mid, False)},
    "x-odd": lambda mid: {"x": (mid, True)},
    "xz-odd": lambda mid: {"x": (mid, True), "z": (0, True)},
    "xyz-even": lambda mid: {"x": (mid, False), "y": (1, False), "z": (0, False)},
}
TARGET_MID = 13
OWNER_MID = 4


def set_planes(game: h.Game, planes: dict) -> None:
    """Only the planes given on the fixture grid, the others removed, and the
    game's symmetry option on"""
    args = {}
    for axis in "xyz":
        if axis in planes:
            p, odd = planes[axis]
            cell = [0, 0, 0]
            cell["xyz".index(axis)] = p
            args[axis], args[f"{axis}_odd"] = cell, odd
        else:
            args[axis], args[f"{axis}_odd"] = None, False
    game.api.set_grid_symmetry(game.grid, **args)
    game.api.set_game_option("cubeBuilderUseSymmetry", True)


def symmetry_off(game: h.Game) -> None:
    game.api.set_game_option("cubeBuilderUseSymmetry", False)


def one_step(history: History, node: dict) -> None:
    """The step is the only one the action added: its parent is the step that
    was current before it"""
    time.sleep(1)
    assert history.current()["id"] == node["id"], history.labels()
    assert history.node(node["parent"]) is not None or node["parent"] == 0


def paste_into_grid(game: h.Game, history: History) -> None:
    """A copy of the target row pasted onto the floor behind it, at z -1: one
    step, undo removes every pasted block and redo pastes them again"""
    grids = lambda: {
        g["entityId"]: g.get("name") for g in game.api.list_grids()
    }  # noqa: E731
    before = grids()
    game.copy(*TARGET_ROW, ctrl=True)
    last = history.build()["current"]
    game.paste_on((15, 0, -1))
    pasted = [(x, 1, -1) for x in range(11, 16)]
    wait_until(lambda: exist(game, pasted), "the paste into the grid")
    node = wait_until(
        lambda: (n := history.current()) and n["id"] != last and n,
        "the paste in the history",
    )
    assert node["parent"] == last, history.labels()
    one_step(history, node)
    game.leave_screens()

    undo(game, history, node)
    wait_until(lambda: gone(game, pasted), "the paste undone")
    assert exist(game, TARGET_CELLS)
    redo(game, history, node)
    wait_until(lambda: exist(game, pasted), "the paste again after the redo")
    undo(game, history, node)
    wait_until(lambda: gone(game, pasted), "the paste undone again")
    try:
        wait_until(lambda: grids().keys() == before.keys(), "the grids", timeout=10)
    except AssertionError:
        raise AssertionError(f"Grids before the paste {before}, now {grids()}")
    assert_references(game)
