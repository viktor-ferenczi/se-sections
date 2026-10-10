"""A vanilla Magnetar server (DirectTransport, no Sections counterpart: that is
se1/tickets/SE1-0068.md) and one Sections client joined to it as an admin.

Needs SECTIONS_SLOT: the server and the client use slot resources ds0 and c1,
so these tests can run beside the offline ones on c0.
SECTIONS_KEEP=1 leaves both running after the run.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import harness  # noqa: E402
import rig  # noqa: E402

KEEP = os.environ.get("SECTIONS_KEEP") == "1"
PLAYER = "SectionsTester"


@pytest.fixture(scope="session")
def api():
    server, client = rig.server(0), rig.client(1)
    rig.stop(client)
    rig.stop_server(server)
    try:
        rig.start_server(server, admins=[client.client_id])
        api = rig.join(client, server, PLAYER, render=True)
        api.set_admin_flag("creativeTools", True)
        yield api
    finally:
        if not KEEP:
            rig.stop(client)
            rig.stop_server(server)


@pytest.fixture
def game(api, request):
    game = harness.Game(api)
    game.spawn(f"Sections {request.node.name}"[:60])
    yield game
    game.leave_screens()
    game.cleanup()
