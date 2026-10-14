"""Section editing and cutaways on a dedicated server running the Sections
companion, with two players: Alice, an admin, and Bob, a plain player.

Cutaways are allowed for every access level here (CutawayAccessLevel None), so
Bob may remove collision on his own grids but not on Alice's. Editing stays
admin only. test_companion_survival.py covers the default access levels.

SECTIONS_SLOT=<n> uv run pytest tests/ds/test_companion.py
"""

import time
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from se_remote import SetOp

import harness as h
import rig
from companion import (
    CHANNEL,
    cell_z,
    DELETE,
    DOORWAY,
    SERVED,
    WALL_ABOVE_LIGHT,
    WALL_BATTERY,
    WALL_LIGHT,
    edit_message,
    fly_through,
    hidden_cells,
    hide_message,
    hits,
    log_has,
    log_has_server,
    wait_until,
    wall,
)
from conftest import ServedGame
from harness import EXPECTED, OWNER_ROW, TARGET_ROW, TARGETS

COMPANION = True
SERVER_CONFIG = {"CutawayAccessLevel": "None"}

DOORWAY_CELLS = {(2, 1, 0), (2, 2, 0), (2, 3, 0)}


def refs(game, grids=None):
    return h.references((grids or game.saved_grids()).values())


@pytest.fixture
def wall_game(api, server):
    """Alice with a wall instead of the reference fixture"""
    game = ServedGame(api, server, rig.client(1))
    game.spawn("Sections wall", wall("Sections wall"))
    yield game
    # Shows everything and turns auto-hide off
    game.press("H", ["LeftControl", "LeftShift"])
    game.leave_screens()
    game.cleanup()


def hide_doorway(game) -> None:
    game.select(*DOORWAY)
    game.press("H")
    game.press("Escape")
    wait_until(
        lambda: hidden_cells(game, game.grid) == DOORWAY_CELLS,
        "the server to know the hidden doorway",
    )


def meet(bob, game) -> None:
    """Bob comes over to work on Alice's grid. Her grid reaches his client once
    he is within the sync distance."""
    bob.grid, bob.origin = game.grid, game.origin
    bob.api.character_teleport(game.origin[0], game.origin[1] + 10, game.origin[2] + 30)
    wait_until(
        lambda: any(g["entityId"] == game.grid for g in bob.api.list_grids()),
        "Alice's grid on Bob's client",
    )
    time.sleep(2)


# --- handshake --------------------------------------------------------------------


def test_both_clients_are_served(game, bob):
    wait_until(lambda: log_has(rig.client(1), SERVED), "Alice to be served")
    wait_until(lambda: log_has(rig.client(2), SERVED), "Bob to be served")
    alice_status = wait_until(game.status, "Alice in the status file")
    assert (alice_status["edit"], alice_status["cutaway"], alice_status["anyGrid"]) == (
        True,
        True,
        True,
    )
    bob_status = wait_until(bob.status, "Bob in the status file")
    assert (bob_status["edit"], bob_status["cutaway"], bob_status["anyGrid"]) == (
        False,
        True,
        False,
    )


# --- editing: the same results as offline (tests/test_references.py) -------------


def test_cut_targets_and_paste_back(game):
    game.cut(*TARGET_ROW, ctrl=True)
    wait_until(
        lambda: not any(game.exists(pos) for pos, _, _ in TARGETS.values()),
        "the cut to remove the targets",
    )
    dangling = h.broken(refs(game))
    assert set(dangling) == {o for o, r in EXPECTED.items() if r}, dangling

    game.paste_on((15, 0, 0))
    wait_until(
        lambda: all(game.exists(pos) for pos, _, _ in TARGETS.values()),
        "the paste to put the targets back",
    )
    assert refs(game) == EXPECTED


def test_cut_owners_and_paste_back(game):
    game.cut(*OWNER_ROW)
    wait_until(lambda: not game.exists(OWNER_ROW[0]), "the cut to remove the owners")
    game.paste_on((0, 0, 0))
    wait_until(lambda: game.exists(OWNER_ROW[0]), "the paste to put the owners back")
    assert refs(game) == EXPECTED


def test_copy_leaves_the_grid_alone(game):
    game.copy(*TARGET_ROW, ctrl=True)
    # The copy comes back from the server; Escape would drop it from the clipboard
    time.sleep(2)
    assert all(game.exists(pos) for pos, _, _ in TARGETS.values())
    pasted = game.paste_free()
    assert len(pasted) == 1, pasted
    grids = game.saved_grids()
    names = set(h.blocks([grids[pasted[0]]]))
    assert names == set(TARGETS), names


def test_delete(game):
    game.delete(*TARGET_ROW, ctrl=True)
    wait_until(
        lambda: not any(game.exists(pos) for pos, _, _ in TARGETS.values()),
        "the delete to remove the targets",
    )
    assert all(game.exists(pos) for pos, _, _ in h.OWNERS.values())


def test_blueprint_is_saved_on_the_client(game):
    folder = rig.client(1).appdata / "Blueprints" / "local" / "Sections"
    before = set(folder.glob("*/bp.sbc")) if folder.exists() else set()
    game.select(*TARGET_ROW)
    game.press("Enter", ["LeftControl"])
    new = wait_until(
        lambda: set(folder.glob("*/bp.sbc")) - before, "the blueprint file", 60
    )
    text = next(iter(new)).read_text(encoding="utf-8")
    for name in TARGETS:
        assert f"<CustomName>{name}</CustomName>" in text, name
    game.leave_screens()


# --- editing refused ---------------------------------------------------------------


def test_bob_cannot_cut(game, bob):
    meet(bob, game)
    bob.cut(*TARGET_ROW, ctrl=True)
    bob.leave_screens()
    time.sleep(2)
    assert all(game.exists(pos) for pos, _, _ in TARGETS.values())


def test_server_refuses_a_raw_edit_from_bob(game, bob):
    """Bob's client would not send it; the server must refuse it anyway, on
    Alice's grid and on a grid of his own"""
    first, last = TARGET_ROW
    box = (min(first[0], last[0]), 0, 0), (max(first[0], last[0]), 1, 0)
    bob.api.send_mod_message(CHANNEL, edit_message(DELETE, game.grid, *box))
    own = bob.spawn("Bob's ship")
    bob.api.send_mod_message(CHANNEL, edit_message(DELETE, own, *box))
    time.sleep(3)
    assert all(game.exists(pos) for pos, _, _ in TARGETS.values())
    assert all(bob.exists(pos, own) for pos, _, _ in TARGETS.values())
    bob.cleanup()


# --- cutaways ------------------------------------------------------------------------


def test_collision_is_removed_for_alice_only(wall_game, bob):
    game = wall_game
    meet(bob, game)
    hide_doorway(game)

    # Alice's aim and character pass, Bob's do not
    assert not hits(game, (2, 2, 0))
    assert hits(bob, (2, 2, 0))
    assert hits(game, (1, 2, 0)), "A block next to the doorway lost collision"

    alice = fly_through(game, (2, 2, 0))
    assert alice["z"] < -1, alice
    # The server agrees: its copy of Alice's character is behind the wall too
    position = game.status()["position"]
    assert cell_z(game, position) < -1, position

    stopped = fly_through(bob, (2, 2, 0))
    assert stopped["z"] > 0, stopped


def test_hidden_blocks_keep_working(wall_game, bob):
    game = wall_game
    meet(bob, game)
    # The light is too thin for the aim ray; select up to the armor above it
    game.select(WALL_BATTERY, WALL_ABOVE_LIGHT)
    game.press("H")
    game.press("Escape")
    wait_until(
        lambda: hidden_cells(game, game.grid)
        == {WALL_BATTERY, WALL_LIGHT, WALL_ABOVE_LIGHT},
        "the server to know the hidden battery and light",
    )
    for player in (game, bob):
        assert player.api.get_block(game.grid, WALL_LIGHT)["isWorking"]
        assert player.api.get_block(game.grid, WALL_BATTERY)["isWorking"]


def test_showing_the_blocks_restores_collision(wall_game):
    game = wall_game
    hide_doorway(game)
    game.press("H", ["LeftControl", "LeftShift"])
    wait_until(lambda: not hidden_cells(game, game.grid), "the server to drop them")
    assert hits(game, (2, 2, 0))
    stopped = fly_through(game, (2, 2, 0))
    assert stopped["z"] > 0, stopped


def test_auto_hide(wall_game):
    game = wall_game
    game.api.character_teleport(*game.world((2, 2, 2)))
    time.sleep(1)
    game.press("OemPipe", ["LeftControl", "LeftAlt"])
    wait_until(
        lambda: (2, 2, 0) in hidden_cells(game, game.grid), "auto-hide on the server"
    )
    alice = fly_through(game, (2, 2, 0))
    assert alice["z"] < -1, alice
    # Clear of the wall, where turning it off is allowed
    game.press("OemPipe", ["LeftControl", "LeftAlt"])
    wait_until(lambda: not hidden_cells(game, game.grid), "auto-hide off on the server")


def test_bob_hides_his_own_grid_but_not_alices(wall_game, bob):
    alices = wall_game.grid
    bob.spawn("Bob's wall", wall("Bob's wall"))
    hide_doorway(bob)
    assert not hits(bob, (2, 2, 0))
    passed = fly_through(bob, (2, 2, 0))
    assert passed["z"] < -1, passed

    # A raw request on Alice's grid is refused and answered with a revoke
    bob.api.send_mod_message(CHANNEL, hide_message(alices, sorted(DOORWAY_CELLS)))
    wait_until(
        lambda: log_has(rig.client(2), "you don't own this grid"), "the server's revoke"
    )
    assert not hidden_cells(bob, alices)
    bob.press("H", ["LeftControl", "LeftShift"])
    bob.cleanup()


# --- server paths: subgrids, reference data, split, ownership, rate limit ---------

GROUP = Path(__file__).resolve().parent.parent / "data" / "block-reference-test.sbc"


def test_cut_takes_orphaned_subgrids_along(api, server, request):
    """The large grid's advanced rotor takes the small grid and its hinge arms
    and solar grids along (tests/test_reference_world.py, offline), here on the
    server; pasted back, the whole group refers to itself as before."""
    expected = h.references(ET.parse(GROUP).getroot().iter("CubeGrid"))
    game = ServedGame(api, server, rig.client(1))
    grids = game.spawn_blueprint(GROUP, f"Sections {request.node.name}"[:60])
    try:
        assert len(grids) == 6
        lg = {api.get_grid(g)["name"]: g for g in grids}["Block Reference Test"]
        assert h.references(game.saved_grids().values()) == expected

        game.cut_block((3, 1, 3), lg, side=(0, 0, -1))
        wait_until(
            lambda: {g["entityId"] for g in api.list_grids()} & set(grids) == {lg},
            "the cut to take the five subgrids along",
            60,
        )
        assert log_has_server(server, "blocks and 5 subgrids")

        game.paste_on((3, 0, 3), lg, alt=True)
        wait_until(lambda: game.exists((3, 1, 3), lg), "the paste back")
        assert h.references(game.saved_grids().values()) == expected
    finally:
        game.leave_screens()
        game.cleanup()


def test_clear_reference_data(game):
    """A copy backs the references up on the server; Minus, after its
    confirmation, clears them there"""
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
    wait_until(
        lambda: log_has_server(game.server, "cleared the block reference data"),
        "the server to clear it",
    )
    assert not any(h.storage(b) for b in h.blocks(game.saved_grids().values()).values())


def test_split_drops_the_blocks_moved_away(wall_game):
    """Deleting the wall's last column splits the battery column off. Its hidden
    blocks belong to another grid now; the server lets go of them."""
    game = wall_game
    hide_doorway(game)
    game.select(WALL_BATTERY, WALL_ABOVE_LIGHT)
    game.press("H")
    game.press("Escape")
    wait_until(
        lambda: hidden_cells(game, game.grid)
        == DOORWAY_CELLS | {WALL_BATTERY, WALL_LIGHT, WALL_ABOVE_LIGHT},
        "the server to know all hidden blocks",
    )
    game.delete((4, 0, 0), (4, 4, 0))
    wait_until(
        lambda: hidden_cells(game, game.grid) == DOORWAY_CELLS,
        "the server to drop the blocks split off",
    )
    assert not hits(game, (2, 2, 0)), "The doorway got its collision back"


def test_ownership_change_revokes_bob(game, bob):
    """Bob hides blocks of his own wall; once Alice owns its functional blocks it
    is no longer his, and the server lets go of the hidden blocks"""
    own = bob.spawn("Bob's wall", wall("Bob's wall"))
    hide_doorway(bob)
    api = game.api
    api.character_teleport(bob.origin[0], bob.origin[1] + 10, bob.origin[2] + 30)
    wait_until(
        lambda: any(g["entityId"] == own for g in api.list_grids()),
        "Bob's wall on Alice's client",
    )
    # The battery is the wall's only owned block. An admin's ownership change
    # goes through at once only with the use terminals admin setting on.
    api.set_admin_flag("useTerminals", True)
    try:
        api.batch(
            sets=[SetOp.owner(own, WALL_BATTERY, steam_id=rig.client(1).client_id)]
        ).set(0)
        wait_until(
            lambda: not hidden_cells(bob, own), "the server to drop Bob's blocks"
        )
    finally:
        api.set_admin_flag("useTerminals", False)
    # Bob's client notices the new owner too and shows the blocks itself; when
    # the server is first, it revokes them. Either way Bob collides again.
    wait_until(lambda: hits(bob, (2, 2, 0)), "Bob's collision back")
    bob.cleanup()


def test_rate_limit_revokes_everything(wall_game):
    """A burst of hide messages over the limit: the server drops what the
    player hid, once, and tells the client to show everything"""
    game = wall_game
    hide_doorway(game)
    empty = hide_message(game.grid, [])
    # In parallel: one request at a time stays within the refill rate
    with ThreadPoolExecutor(32) as pool:
        list(pool.map(lambda _: game.api.send_mod_message(CHANNEL, empty), range(600)))
    wait_until(lambda: not hidden_cells(game, game.grid), "the server to drop them")
    wait_until(
        lambda: log_has(
            rig.client(1),
            "The server restored the blocks of all grids: too many requests",
        ),
        "the revoke on the client",
    )
    revokes = (
        rig.client(1)
        .log.read_text(errors="replace")
        .count("The server restored the blocks of all grids: too many requests")
    )
    assert revokes <= 10, revokes
    wait_until(lambda: hits(game, (2, 2, 0)), "collision back on the client")


def test_cleanup_when_alice_leaves(api, server):
    game = ServedGame(api, server, rig.client(1))
    game.before = {g["entityId"] for g in api.list_grids()}
    game.spawn("Sections wall", wall("Sections wall"))
    hide_doorway(game)
    rig.stop(rig.client(1))
    wait_until(
        lambda: rig.client(1).client_id not in rig.server_status(server),
        "the server to drop Alice",
        120,
    )
