"""Restoring references across a mechanical group of six grids, large and small.

The group comes from Viktor's manual test world (data/block-reference-test.sbc,
made by data/make_reference_blueprint.py): a static large grid (LG), a small
grid (SG) on its advanced rotor, and on SG two rotors with hinge arms carrying
solar grids. Blocks on every level refer to blocks on the others: toolbars of a
cockpit, timers, sensors, defensive combat blocks, event controllers and a
button panel, the remote control's camera, event controller selections, both
turret controllers' rotors, hinges, cameras and guns, the offensive combat
block's weapons and the AI recorder's waypoint actions.

Each test cuts one section, pastes it back onto its grid, and expects every
reference of the group to be what the blueprint says. The pastes hold Alt:
the placement test takes each pasted grid for a solid box, and the grids of
this group overlap that way. The cells checked afterwards show the paste is exact.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import harness as h

BLUEPRINT = Path(__file__).with_name("data") / "block-reference-test.sbc"


def normalized(refs):
    """Turret controllers keep stale tools next to the restored ones
    (se1/tickets/SE1-0106.md); compare the set of valid ones"""
    for items in refs.values():
        if "tools" in items:
            items["tools"] = sorted({t for t in items["tools"] if t})
    return refs


EXPECTED = normalized(h.references(ET.parse(BLUEPRINT).getroot().iter("CubeGrid")))


AROUND = [(0, 0, 1), (-1, 0, 0), (0, 0, -1), (1, 0, 0)]


@pytest.fixture
def group(api, request):
    game = h.Game(api)
    grids = game.spawn_blueprint(BLUEPRINT, f"Sections {request.node.name}"[:60])
    assert len(grids) == 6
    names = {api.get_grid(g)["name"]: g for g in grids}
    game.lg, game.sg = names["Block Reference Test"], names["Block Reference Test SG"]
    yield game
    game.leave_screens()
    game.cleanup()


def refs(game):
    return normalized(h.references(game.saved_grids().values()))


def test_group_reads_back(group):
    assert len(EXPECTED) == 15
    assert refs(group) == EXPECTED


def test_cut_main_rotor_and_paste_back(group):
    """The large grid's advanced rotor takes SG and all its subgrids along. The
    large grid's blocks refer into them, and theirs refer back."""
    group.cut_block((3, 1, 3), group.lg, side=(0, 0, -1))
    assert not group.exists((3, 1, 3), group.lg)
    dangling = h.broken(refs(group))
    assert {"Cockpit LG", "Timer LG", "Sensor LG"} <= set(dangling), dangling
    group.paste_on((3, 0, 3), group.lg, alt=True)
    assert group.exists((3, 1, 3), group.lg)
    assert refs(group) == EXPECTED


def test_cut_subgrid_rotor_and_paste_back(group):
    """A rotor on SG takes its hinge arm and solar grid along, two levels down"""
    # The hinge arm swings and may hide the rotor from one side
    group.cut_block((-14, 7, 1), group.sg, side=AROUND)
    assert not group.exists((-14, 7, 1), group.sg)
    dangling = h.broken(refs(group))
    assert "Custom Turret Controller LG Solar 1" in dangling, dangling
    group.paste_on((-14, 6, 1), group.sg, alt=True)
    assert group.exists((-14, 7, 1), group.sg)
    assert refs(group) == EXPECTED


def test_cut_large_grid_owners_and_paste_back(group):
    """Cockpit, rotating light, LCD and turret controller of the large grid"""
    group.cut((-1, 1, 3), (0, 1, 6), grid=group.lg, side=(-1, 0, 0))
    assert not group.exists((0, 1, 6), group.lg)
    group.paste_on((0, 0, 6), group.lg, alt=True)
    assert group.exists((0, 1, 6), group.lg)
    assert refs(group) == EXPECTED


def test_cut_small_grid_owner_and_paste_back(group):
    """SG's event controller selects the large grid's cockpit and switches the
    target timer next to it on SG. A paste onto a side face of this dynamic grid
    makes a grid of its own, so it goes back onto the deck below it."""
    group.cut_block((-2, 3, 0), group.sg, side=(0, 0, -1))
    assert not group.exists((-2, 3, 0), group.sg)
    assert "Event Controller SG" not in refs(group)
    # The pasted owner carries remapped ids that point nowhere until restored
    group.paste_on((-2, 2, 0), group.sg, alt=True, distance=2.5)
    assert group.exists((-2, 3, 0), group.sg)
    assert refs(group) == EXPECTED
