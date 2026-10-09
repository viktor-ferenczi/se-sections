"""Build and rebuild scenarios: sections deleted and pasted back, cut and pasted
back several times, copied onto the same grid and into empty space, and saved
as blueprints.

Run against an isolated client: SECTIONS_SLOT=<n> uv run pytest tests
"""

from pathlib import Path

import pytest

import harness as h
from harness import EXPECTED, OWNER_ROW, TARGET_ROW, TARGETS


def refs(game, grids=None):
    return h.references((grids or game.saved_grids()).values())


def local_blueprints(game) -> Path:
    # The world is in <appdata>/Saves/tests/<world>
    return Path(game.api.get_state()["path"]).parents[2] / "Blueprints" / "local"


def assert_restored(game, grids=None):
    assert h.without_turret_gaps(refs(game, grids)) == h.without_turret_gaps(EXPECTED)


# Without Ctrl the 1x2x1 rotor stators stay out of a one block high box
FLAT_TARGETS = [pos for pos, kind, _ in TARGETS.values() if kind != "MotorStator"]


def test_delete_then_paste_copy_back(game):
    """Copy, delete with Backspace, then rebuild from the clipboard"""
    game.copy(*TARGET_ROW)
    game.leave_screens()
    game.delete(*TARGET_ROW)
    assert not any(game.exists(pos) for pos in FLAT_TARGETS)
    assert h.broken(refs(game))
    # The clipboard still holds the copy. The rotor stators stayed in the gap of
    # the section, so the placement test needs to be off.
    game.press("V", ["LeftControl"])
    game.paste_on((15, 0, 0), alt=True)
    assert all(game.exists(pos) for pos in FLAT_TARGETS)
    assert_restored(game)


@pytest.mark.xfail(
    strict=True, reason="Ctrl+Backspace does nothing, se1/tickets/SE1-0108.md"
)
def test_ctrl_inverts_delete(game):
    game.delete(*TARGET_ROW, ctrl=True)
    assert not game.exists(TARGETS["Azimuth"][0])


def test_repeated_cut_and_paste_back(game):
    """Each round trip restores, and the blocks keep their GUIDs"""
    guids = None
    for _ in range(3):
        game.cut(*TARGET_ROW, ctrl=True)
        assert not game.exists(TARGET_ROW[0])
        game.paste_on((15, 0, 0))
        grids = game.saved_grids()
        assert_restored(game, grids)
        named = h.blocks(grids.values())
        current = {name: h.guid(named[name]) for name in TARGETS}
        assert guids is None or current == guids
        guids = current


def test_cut_whole_row_and_paste_back(game):
    """Owners and targets cut together keep their references among themselves"""
    game.cut(OWNER_ROW[1], TARGET_ROW[1], ctrl=True)
    assert not game.exists(OWNER_ROW[1])
    game.paste_on((15, 0, 0))
    assert game.exists(OWNER_ROW[1])
    assert_restored(game)


def test_copy_into_empty_space(game):
    """A copy pasted as a grid of its own refers to its own blocks, and the
    original keeps referring to the original blocks"""
    original = game.grid
    game.copy(OWNER_ROW[1], TARGET_ROW[1], ctrl=True)
    pasted = game.paste_free()
    assert pasted, "The copy did not paste"
    grids = game.saved_grids()
    assert_restored(game, {original: grids[original]})
    copy = {g: grids[g] for g in pasted if g in grids}
    assert copy
    assert_restored(game, copy)
    copied = h.blocks(copy.values())
    assert all(h.guid(copied[name]) for name in EXPECTED)


def test_duplicate_on_the_same_grid(game):
    """A second copy of the targets on the same grid gets GUIDs of its own, so
    the owners keep pointing at the originals, and those still restore"""
    # Without the rotors, whose heads would touch the original ones
    game.copy(*TARGET_ROW)
    game.paste_on((15, 0, -1))
    assert game.exists((15, 1, -1))
    grids = game.saved_grids()
    named = h.blocks(grids.values())
    duplicates = [n for n in named if " #" in n]
    assert len(duplicates) == len(FLAT_TARGETS), duplicates
    guids = [h.guid(b) for b in named.values()]
    assert len(set(guids)) == len(guids), "Duplicate GUIDs on one grid"
    # Owners refer to the blocks at z 0, not to the duplicates behind them
    for name, block in named.items():
        if name in TARGETS:
            assert block.find("Min").get("z", "0") == "0", name
    assert_restored(game, grids)

    # The placement test rejects pasting the section back next to the
    # duplicates, so it is turned off; the cells show the paste is exact
    game.cut(*TARGET_ROW, ctrl=True)
    game.paste_on((15, 0, 0), alt=True)
    assert all(game.exists(pos) for pos, _, _ in TARGETS.values())
    assert_restored(game)


def test_blueprint_carries_reference_data(game):
    """Enter saves the section as a local blueprint with the block reference data"""
    blueprints = (
        Path(game.api.get_state()["path"]).parents[2]
        / "Blueprints"
        / "local"
        / "Sections"
    )
    before = set(blueprints.glob("*/bp.sbc")) if blueprints.exists() else set()
    game.select(*TARGET_ROW)
    game.press("Enter")
    game.leave_screens()
    added = set(blueprints.glob("*/bp.sbc")) - before
    assert len(added) == 1, added
    text = added.pop().read_text(encoding="utf-8")
    named = h.blocks(game.saved_grids().values())
    for name in ("Battery A", "Battery B", "Camera"):
        assert h.guid(named[name]) in text, name
    assert h.STORAGE_KEY in text


def test_blueprint_pasted_back(game):
    """A section blueprint (Enter) loaded through the Blueprints screen restores
    the references of the blocks it brings back, from the data in the file"""
    blueprints = local_blueprints(game) / "Sections"
    before = set(blueprints.glob("*/bp.sbc")) if blueprints.exists() else set()
    game.select(*TARGET_ROW)
    game.press("Enter")
    game.leave_screens()
    added = set(blueprints.glob("*/bp.sbc")) - before
    assert len(added) == 1, added
    game.delete(*TARGET_ROW)
    assert not any(game.exists(pos) for pos in FLAT_TARGETS)
    assert h.broken(refs(game))
    game.blueprint_to_clipboard("Sections", added.pop().parent.name)
    # The rotor stators stayed in the gap of the section
    game.paste_on((15, 0, 0), alt=True)
    assert all(game.exists(pos) for pos in FLAT_TARGETS)
    assert_restored(game)
