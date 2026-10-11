"""One isolated rendering client for the whole run, on a fresh copy of the test
world. Sections draws its selection, which crashes a --no-render client. A test
module that needs other Sections settings sets SECTIONS_SETTINGS, and the client
restarts with them.

SECTIONS_ATTACH=1 uses a client that is already running (rig.py start) and
skips the modules that set SECTIONS_SETTINGS. SECTIONS_KEEP=1 leaves the client
running after the run.
"""

from __future__ import annotations

import os

import pytest

import harness
import rig

ATTACH = os.environ.get("SECTIONS_ATTACH") == "1"
KEEP = os.environ.get("SECTIONS_KEEP") == "1"


@pytest.fixture(scope="session")
def start_client():
    client = rig.client(0)
    running = {}

    def start(settings: dict):
        if ATTACH:
            return rig.connect(client)
        if running.get("settings") != settings:
            rig.stop(client)
            running["settings"] = settings
            running["api"] = rig.start_offline(client, render=True, sections=settings)
        return running["api"]

    try:
        yield start
    finally:
        if not ATTACH and not KEEP:
            rig.stop(client)


@pytest.fixture(scope="module")
def api(start_client, request):
    settings = getattr(request.module, "SECTIONS_SETTINGS", {})
    if ATTACH and settings:
        pytest.skip(f"Needs a client started with {settings}")
    return start_client(settings)


@pytest.fixture
def game(api, request):
    """A fresh fixture ship for each test, removed afterwards"""
    game = harness.Game(api)
    game.spawn(f"Sections {request.node.name}"[:60])
    yield game
    game.leave_screens()
    game.cleanup()
