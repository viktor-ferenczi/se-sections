# In-game cutaway checks

Run `test_cutaway.py` against a disposable creative world with the Remote and
Sections plugins enabled. Keep rendering enabled: the test uses real keyboard
and mouse input, collision raycasts, character thrust, and screenshots.

Enable copy/paste in the world. In Sections settings, disable cut confirmation
for this unattended run. Keep opacity at 10%. The test creates its own dynamic
grid far from the test world's existing ships.

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

`test_cutaway_lifecycle.py` separately checks **Ctrl+Shift+J** and saves/reloads
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
