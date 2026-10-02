# In-game cutaway checks

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

```bash
SE_REMOTE_URL=http://127.0.0.1:24188 \
  /home/viktor/.codex/skills/se-remote/.venv/bin/python tests/test_cutaway.py
```

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
the configured sphere. Increasing 7.5 m to 7.6 m must remove its collision
without changing the configuration. Disabling/re-enabling must reload the
default, and editing the default while active must take effect only on the next
enable. It also checks decreasing by 0.1 m and takes no screenshots.

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
