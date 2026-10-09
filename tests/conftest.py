"""One isolated rendering client for the whole run, on a fresh copy of the test
world. Sections draws its selection, which crashes a --no-render client.

SECTIONS_ATTACH=1 uses a client that is already running (rig.py start), and
SECTIONS_KEEP=1 leaves the client running after the run.
"""

from __future__ import annotations

import os

import pytest

import harness
import rig

ATTACH = os.environ.get("SECTIONS_ATTACH") == "1"
KEEP = os.environ.get("SECTIONS_KEEP") == "1"


@pytest.fixture(scope="session")
def api():
    client = rig.client(0)
    if ATTACH:
        yield rig.connect(client)
        return
    rig.stop(client)
    try:
        yield rig.start_offline(client, render=True)
    finally:
        if not KEEP:
            rig.stop(client)


@pytest.fixture
def game(api, request):
    """A fresh fixture ship for each test, removed afterwards"""
    game = harness.Game(api)
    game.spawn(f"Sections {request.node.name}"[:60])
    yield game
    game.leave_screens()
    game.cleanup()
