"""The "Restore toolbars" setting turned off: Sections neither backs up nor
restores block references.

Run against an isolated client: SECTIONS_SLOT=<n> uv run pytest tests
"""

import harness as h
from harness import EXPECTED, TARGET_ROW

SECTIONS_SETTINGS = {"RestoreToolbars": "false"}


def test_cut_and_paste_back(game):
    game.cut(*TARGET_ROW, ctrl=True)
    assert not game.exists(TARGET_ROW[0])
    game.paste_on((15, 0, 0))
    assert game.exists(TARGET_ROW[0])
    grids = game.saved_grids().values()
    assert h.references(grids) != EXPECTED
    assert [name for name, block in h.blocks(grids).items() if h.storage(block)] == []
