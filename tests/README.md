# Sections tests

The tests drive the game through the Remote plugin, with real keyboard and
mouse input. They need Linux, the game, Pulsar in `~/.config/Pulsar` and the
Remote plugin's working copy next to this repository (`../remote`). Pulsar
compiles Remote and Sections from the working copies.

## Isolated clients and servers

`rig.py` starts its own headless clients and servers, so the tests can run
while other sessions test on the same machine. Their ports, client ids and
folders come from a test slot of the workspace, see
`se/notes/parallel-test-work/NOTE.md`:

```bash
~/ws/se/notes/parallel-test-work/slot.sh claim my-task   # prints the slot number
export SECTIONS_SLOT=11
```

Client 0 of the slot runs the offline tests, client 1 and server 0 the
dedicated server tests. Their folders are `~/.se-test/<task>-c0`, `-c0-data`,
`-c1`, `-c1-data` and `-ds0`; the first launch creates them. Every launch goes
through `run-test.sh`, which waits until it leaves 8 GiB of RAM free. A
client needs about 5.5 GiB and the server about 4 GiB.

The clients render, at 1280x720: Sections draws its selection, and that
crashes a client started with `--no-render`. Without `SECTIONS_SLOT` the rig
uses the single client of the older checks, `~/.se-test/sections` on port 24188.
Release the slot when you are done (`slot.sh release 11`).

## Block references and rebuilding

```bash
uv run pytest tests                  # offline, about 5 minutes
uv run pytest tests/ds               # dedicated server
```

The run starts a client, loads a fresh copy of the Remote suite's space world
(creative, copy and paste on) and stops the client at the end.
`SECTIONS_KEEP=1` leaves it running, and `SECTIONS_ATTACH=1` runs the tests
on a client that is already running, for example one started with
`python tests/rig.py start --render`.

Each test pastes its own fixture ship (`harness.py`). Ten blocks that refer
to other blocks stand in one row: timer, cockpit, sensor, button panel, event
controller, remote control, turret controller, defensive combat, flight
movement and offensive combat blocks. Their targets stand in a second row:
two batteries, a camera and two rotors with heads. The tests cut, copy,
delete and paste these rows with Sections and real input, then save the world
and read the toolbars, the block references and the Sections block reference
data from the save. The save is the only place where the game exposes them.

`test_references.py` covers:

- cutting the targets and pasting them back onto the grid, which restores
  toolbar slots, the remote control's camera, the event controller's
  selection and the turret controller's rotors and camera, with the rotor
  heads coming along as subgrids;
- cutting the owners and pasting them back;
- the reference data a backup writes (each block's GUID and the GUIDs it
  refers to), that GUIDs survive further backups, and clearing the data with
  the minus key.

`test_rebuild.py` covers deleting a section and pasting a copy back (with
Alt to skip the placement test), three cut and paste rounds in a row, cutting
owners and targets together, a copy pasted into empty space, a duplicate
pasted onto the same grid (it gets new GUIDs and the owners keep pointing at
the originals), and the reference data in a section blueprint (Enter).

Known defects are expected failures, tied to their tickets:
`se1/tickets/SE1-0105.md` (crash restoring a turret controller's rotor without
a head, not run), `SE1-0106.md` (turret controller toolbar and tools) and
`SE1-0108.md` (Ctrl does not invert Delete). The game itself does not save the
flight movement block's toolbar, so it is not checked.

`tests/ds/test_multiplayer.py` joins a client to a vanilla Magnetar server
over DirectTransport. Sections has no server counterpart yet
(`se1/tickets/SE1-0068.md`), so section editing is refused on a client of a
dedicated server and nothing restores references there. The tests check that
the client runs Sections and that copy, cut and delete leave the grid and the
clipboard alone.

Not covered: the offensive combat block's weapon list and the AI recorder's
waypoint toolbars, which live in component data the fixture does not write,
and pasting a section blueprint back through the Blueprints screen.

# In-game cutaway checks

The scripts below are older, one by one checks. Start a client for them with
the settings each one expects, run the script, then stop the client:

```bash
SECTIONS_SLOT=11 uv run python tests/rig.py start --render
SECTIONS_SLOT=11 uv run python tests/test_cutaway.py
SECTIONS_SLOT=11 uv run python tests/rig.py stop
```

`rig.py start` takes `Key=Value` arguments for `Sections.cfg`, for example
`CutConfirmation=true` for `test_single_block.py`. By default it turns cut and
delete confirmation off, sets opacity to 10% and saturation to 100%, and keeps
the default key bindings. `--earth` loads the Remote suite's Earth world,
which these scripts expect; their `aim` assumes an upright character.

On 2026-10-09 (Linux, a fresh slot client per script) all scripts passed
except three. `test_cutaway.py` fails at the hidden battery step and
`test_auto_hide_safety.py` at its last reload, both as described in
`se1/notes/sections-cutaway/NOTE.md`. `test_auto_hide.py` fails at its final
aim when the client is fresh and its character starts rolled. It passed when
it ran after other scripts on the same client.

Run `test_cutaway.py` against a disposable creative world with the Remote and
Sections plugins enabled. Keep rendering enabled: the test uses real keyboard
and mouse input, collision raycasts, character thrust, and screenshots.

Enable copy/paste in the world. In Sections settings, disable cut confirmation
for this unattended run. Keep opacity at 10%. The test creates its own dynamic
grid far from the test world's existing ships.

Use the current cutaway bindings: **H** hides, **Shift+H** shows, **Alt+H**
restores one grid, and **Ctrl+Shift+H** restores all grids. Existing `Sections.cfg`
files retain earlier bindings, so set these in the plugin configuration before
running the tests; rebuilding the plugin does not replace saved bindings.

The default run expects **Include intersecting blocks** to be off. To test the
opposite configuration, enable it in the plugin settings and run with
`SECTIONS_INCLUDE_INTERSECTING=1`. This environment variable describes the
configured setting; it does not change it. `SECTIONS_TEST_OUTPUT` selects the
folder for screenshots and results (default `/tmp/sections-test-results`).

The checks cover accumulating and subtracting boxes, flying through hidden
armor, multi-cell block bounds, Ctrl inversion for hiding and the copy/cut mouse
buttons, functional hidden blocks, preserving saved colors, whole-grid recovery,
copying without transferring the mask, and replacement blocks starting solid.

Two multiplayer clients are still needed to check ownership restrictions,
admin permissions, and another player's unchanged view across a real connection.

`test_selection_input.py` requires a disposable creative world and the default
bindings. It checks repeated H/Shift+H presses, movement, and normal H/Enter
handling after leaving selection. Ctrl+Shift+H must restore the manual mask,
stop auto-hide while outside blocks, and leave HUD signals unchanged during
selection, after clearing it, and on repeated presses. It does not take screenshots.
Also verify that Ctrl+Shift+H does not toggle the rendering profiler; plain
Ctrl+H outside selection should still toggle it.

`test_auto_hide_radius.py` checks the active radius against a cube just beyond
the configured sphere. Increasing 7.5 m to 8.0 m must remove its collision
without changing the configuration. Disabling/re-enabling must reload the
default, and editing the default while active must take effect only on the next
enable. It also checks decreasing by 0.5 m and takes no screenshots.

`test_cutaway_lifecycle.py` separately checks **Ctrl+Shift+H** and saves/reloads
the world while a cutaway and auto-hide are active, then checks restored
collision and saved block colors. This test writes the world, so use only
disposable test data.

Run `test_auto_hide.py` with auto-hide off and the Remote + Sections test
profile. It tests the native config dialog, radius endpoints and rounding,
all three rebound shortcuts, the default shortcuts, sphere movement,
preservation of manual masks, and the show-all button. It restores the default
auto-hide bindings and radius, and leaves auto-hide off. It also sets
**Include intersecting blocks** off, opacity to 10%, and saturation to 100%.

The main-menu permission check was performed separately: opening Sections
settings and checking **Auto-hide blocks** outside a loaded world immediately
reverts the checkbox to off.

`test_settings_sliders.py` checks real Ctrl-click numeric entry at 1280×720,
confirmation, cancellation, integer and float settings, and the radius dialog's
0.1 m increment buttons. It restores the values it changes. This regression
reproduced the crash caused by looking up the obsolete `m_canHideOthers` field.

`test_auto_hide_safety.py` checks shutdown refusal inside a block and at its
outer boundary, config checkbox/reset behavior, global recovery, successful
shutdown after moving clear, and forced cleanup on reload. The refusal message
is captured for visual inspection. Run only in a disposable world: this test
reloads without saving.

`test_auto_hide_building.py` flies into a row of armor with auto-hide on, then
builds and removes a block beyond the sphere with real mouse input while the
aim ray passes through hidden blocks. The new block must land on the visible
block's face, and only the visible block may be removed. Start it with auto-hide
off. It only needs the default bindings.

`test_single_block.py` highlights one block of the fixture with **NumPad 0**,
copies it with **Insert** and cuts it with **Delete**, then pastes the clipboard
to check it holds exactly that block. It expects cut confirmation to be on and
the default bindings.
