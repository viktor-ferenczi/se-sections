"""Restoring block toolbar slots and block references when sections are cut
and pasted back onto their grid.

Run against an isolated client: SECTIONS_SLOT=<n> uv run pytest tests
"""

import harness as h
from harness import EXPECTED, TARGET_ROW, OWNER_ROW, TARGETS


def refs(game, grids=None):
    return h.references((grids or game.saved_grids()).values())


def cut_targets_and_paste_back(game):
    game.cut(*TARGET_ROW, ctrl=True)
    assert not any(game.exists(pos) for pos, _, _ in TARGETS.values())
    dangling = h.broken(refs(game))
    game.paste_on((15, 0, 0))
    assert all(game.exists(pos) for pos, _, _ in TARGETS.values())
    return dangling


def test_fixture_reads_back(game):
    """The oracle: the saved world has the fixture's references, and nothing
    has written block reference data yet"""
    grids = game.saved_grids()
    assert refs(game, grids) == EXPECTED
    assert not any(h.storage(b) for b in h.blocks(grids.values()).values())


def test_cut_targets_and_paste_back(game):
    dangling = cut_targets_and_paste_back(game)
    # Every owner lost its references with the cut, which proves the restore
    assert set(dangling) == {o for o, r in EXPECTED.items() if r}, dangling

    assert refs(game) == EXPECTED


def test_cut_owners_and_paste_back(game):
    """The pasted owners carry remapped ids that point nowhere until restored"""
    game.cut(*OWNER_ROW)
    assert not game.exists(OWNER_ROW[0])
    game.paste_on((0, 0, 0))
    assert refs(game) == EXPECTED


def test_turret_toolbar_restored(game):
    cut_targets_and_paste_back(game)
    assert refs(game)["Turret"]["slot 0"] == "Battery B"


def test_turret_tools_restored_without_stale_entries(game):
    """The ids of the cut tools are dropped, not kept next to the restored ones"""
    cut_targets_and_paste_back(game)
    assert refs(game)["Turret"]["tools"] == ["Battery A", "Battery B"]


def test_turret_rotor_without_head(game):
    """The fixture's rotors have no heads. Binding such a rotor through the
    game's setters used to crash the game (se1/tickets/SE1-0105.md)."""
    cut_targets_and_paste_back(game)
    assert game.api.get_state()["ready"]
    turret = refs(game)["Turret"]
    assert (turret["azimuth"], turret["elevation"]) == ("Azimuth", "Elevation")


def test_reference_data_written_on_backup(game):
    """A copy backs up every terminal block of the grid: its own GUID, and for
    each reference the GUID of the block it refers to"""
    game.copy(*TARGET_ROW)
    game.leave_screens()
    named = h.blocks(game.saved_grids().values())
    guids = {name: h.guid(block) for name, block in named.items()}
    assert all(guids.values()), guids
    assert len(set(guids.values())) == len(guids), "GUIDs are not unique"

    cockpit = h.storage(named["Cockpit"])
    assert "[Toolbar]" in cockpit
    for slot, target in EXPECTED["Cockpit"].items():
        assert f"{slot.split()[1]}:{guids[target]}" in cockpit, cockpit
    assert f"Camera:{guids['Camera']}" in h.storage(named["Remote"])
    event = h.storage(named["Event"])
    assert "[EventController]" in event
    assert guids["Battery A"] in event and guids["Battery B"] in event
    turret = h.storage(named["Turret"])
    for key, target in (
        ("AzimuthRotor", "Azimuth"),
        ("ElevationRotor", "Elevation"),
        ("Camera", "Camera"),
    ):
        assert f"{key}:{guids[target]}" in turret, turret
    assert "Name0:Lamp" in h.storage(named["Buttons"])


def test_backup_keeps_guids(game):
    """A second backup keeps the GUIDs of the first, so older copies still match"""
    game.copy(*TARGET_ROW)
    game.leave_screens()
    first = {n: h.guid(b) for n, b in h.blocks(game.saved_grids().values()).items()}
    game.copy(*OWNER_ROW)
    game.leave_screens()
    second = {n: h.guid(b) for n, b in h.blocks(game.saved_grids().values()).items()}
    assert first == second


def test_clear_reference_data(game):
    """Minus while choosing the first corner clears the data from the grid and its
    subgrids, after a confirmation that cannot be turned off"""
    game.copy(*TARGET_ROW)
    game.leave_screens()
    assert all(h.storage(b) for b in h.blocks(game.saved_grids().values()).values())

    game.aim(OWNER_ROW[1])
    game.press("NumPad0")
    game.press("OemMinus")
    screen = game.api.get_focused_screen()
    assert "MessageBox" in screen["type"], screen
    game.api.control_click(text="Yes")
    game.leave_screens()
    assert not any(h.storage(b) for b in h.blocks(game.saved_grids().values()).values())
