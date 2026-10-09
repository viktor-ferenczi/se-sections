"""Shared steps of the block reference and rebuild tests.

The fixture is a ship whose blocks refer to each other in every way Sections
backs up: toolbars, the remote control's camera, the event controller's
selection, the turret controller's rotors, camera and tools. The tests drive
Sections with real input and read the outcome from the saved world, the only
place the game exposes toolbars, block references and mod storage.
"""

from __future__ import annotations

import itertools
import math
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import rig  # noqa: F401 -- puts the Remote client on the path
from se_remote import CallOp, RemoteAPI

XSI = "{http://www.w3.org/2001/XMLSchema-instance}type"
# Mod storage key of the Sections block reference data (ClientPlugin/Logic/ModStorage.cs)
STORAGE_KEY = "cd844fa4-4ac0-4d9c-8a01-73416b225772"
CENTER = (640, 360)
# Fixture places on a 100 m raster, unique across runs in the same world. Not
# much farther out: single precision positions make the aim ray start inside
# the character beyond about a million metres.
_places = itertools.count(int(time.time()) % 10000)

# Owners on top of the floor at y 1, targets after a gap. Each owner refers to
# targets only, so cutting either row leaves dangling references behind.
OWNERS = {
    "Timer": ((0, 1, 0), "TimerBlock", "TimerBlockLarge"),
    "Cockpit": ((1, 1, 0), "Cockpit", "LargeBlockCockpit"),
    "Sensor": ((2, 1, 0), "SensorBlock", "LargeBlockSensor"),
    "Buttons": ((3, 1, 0), "ButtonPanel", "ButtonPanelLarge"),
    "Event": ((4, 1, 0), "EventControllerBlock", "EventControllerLarge"),
    "Remote": ((5, 1, 0), "RemoteControl", "LargeBlockRemoteControl"),
    "Turret": ((6, 1, 0), "TurretControlBlock", "LargeTurretControlBlock"),
    "Defensive": ((7, 1, 0), "DefensiveCombatBlock", "LargeDefensiveCombat"),
    "Flight": ((8, 1, 0), "FlightMovementBlock", "LargeFlightMovement"),
    "Offensive": ((9, 1, 0), "OffensiveCombatBlock", "LargeOffensiveCombat"),
}
TARGETS = {
    "Battery A": ((11, 1, 0), "BatteryBlock", "LargeBlockBatteryBlock"),
    "Camera": ((12, 1, 0), "CameraBlock", "LargeCameraBlock"),
    "Azimuth": ((13, 1, 0), "MotorStator", "LargeStator"),
    "Elevation": ((14, 1, 0), "MotorStator", "LargeStator"),
    "Battery B": ((15, 1, 0), "BatteryBlock", "LargeBlockBatteryBlock"),
}
# The floor row behind, at z -1, is free room for pasting duplicates
FLOOR = [(x, 0, z) for x in range(16) for z in (0, -1)]
OWNER_ROW = ((9, 1, 0), (0, 1, 0))
TARGET_ROW = ((11, 1, 0), (15, 1, 0))
IDS = {name: 900000000000101 + i for i, name in enumerate([*OWNERS, *TARGETS])}

# What every owner refers to, by block name: toolbar slots, camera, selection,
# rotors and tools, as `references` reads them back
EXPECTED = {
    "Timer": {"slot 0": "Battery A"},
    "Cockpit": {"slot 0": "Battery A", "slot 1": "Battery B", "slot 2": "Camera"},
    "Sensor": {"slot 0": "Battery B"},
    "Buttons": {"slot 0": "Battery A", "button names": ["0:Lamp"]},
    "Event": {"slot 0": "Battery B", "selected": ["Battery A", "Battery B"]},
    "Remote": {"camera": "Camera"},
    "Turret": {
        "slot 0": "Battery B",
        "azimuth": "Azimuth",
        "elevation": "Elevation",
        "camera": "Camera",
        "tools": ["Battery A", "Battery B"],
    },
    "Defensive": {"slot 0": "Battery A"},
    "Offensive": {"slot 0": "Battery A"},
}


def _slot(index: int, target: str, action: str = "OnOff") -> str:
    return (
        f"<Slot><Index>{index}</Index><Item />"
        '<Data xsi:type="MyObjectBuilder_ToolbarItemTerminalBlock">'
        f"<Action>{action}</Action><BlockEntityId>{IDS[target]}</BlockEntityId></Data></Slot>"
    )


def _toolbar(kind: str, *slots: str) -> str:
    return f'<Toolbar><ToolbarType>{kind}</ToolbarType><SelectedSlot xsi:nil="true" /><Slots>{"".join(slots)}</Slots></Toolbar>'


EXTRA = {
    "Timer": _toolbar("Character", _slot(0, "Battery A")) + "<Delay>3000</Delay>",
    "Cockpit": _toolbar(
        "Ship", _slot(0, "Battery A"), _slot(1, "Battery B"), _slot(2, "Camera", "View")
    ),
    "Sensor": _toolbar("Character", _slot(0, "Battery B"))
    + "<DetectPlayers>false</DetectPlayers>",
    "Buttons": _toolbar("Character", _slot(0, "Battery A"))
    + "<AnyoneCanUse>true</AnyoneCanUse><CustomButtonNames><dictionary>"
    "<item><Key>0</Key><Value>Lamp</Value></item></dictionary></CustomButtonNames>",
    "Event": _toolbar("Character", _slot(0, "Battery B"))
    + f"<SelectedBlocks><long>{IDS['Battery A']}</long><long>{IDS['Battery B']}</long></SelectedBlocks>",
    "Remote": f"<BindedCamera>{IDS['Camera']}</BindedCamera>",
    # The game's remap of a pasted turret controller fails without a toolbar.
    # Sections backs up its rotors, camera and tools, not its toolbar.
    "Turret": _toolbar("Character", _slot(0, "Battery B"))
    + f"<AzimuthId>{IDS['Azimuth']}</AzimuthId><ElevationId>{IDS['Elevation']}</ElevationId>"
    f"<CameraId>{IDS['Camera']}</CameraId>"
    f"<ToolIds><long>{IDS['Battery A']}</long><long>{IDS['Battery B']}</long></ToolIds>",
    "Defensive": _toolbar("Character", _slot(0, "Battery A")),
    "Offensive": _toolbar("Character", _slot(0, "Battery A")),
    "Battery A": "<CurrentStoredPower>3</CurrentStoredPower><ProducerEnabled>true</ProducerEnabled>",
    "Battery B": "<CurrentStoredPower>3</CurrentStoredPower><ProducerEnabled>true</ProducerEnabled>",
}


# Mounted with their backs on the floor; a block that is not mounted splits off
# at the first removal
FACING_UP = {"Sensor", "Camera"}


def _block(
    kind: str, subtype: str, pos, extra: str = "", entity_id: int = 0, up: bool = False
) -> str:
    entity = f"<EntityId>{entity_id}</EntityId>" if entity_id else ""
    x, y, z = pos
    return (
        f'<MyObjectBuilder_CubeBlock xsi:type="MyObjectBuilder_{kind}">'
        f'<SubtypeName>{subtype}</SubtypeName>{entity}<Min x="{x}" y="{y}" z="{z}" />'
        + (
            '<BlockOrientation Forward="Up" Up="Backward" />'
            if up
            else '<BlockOrientation Forward="Forward" Up="Up" />'
        )
        + f'<ColorMaskHSV x="0.55" y="0.4" z="0.2" />{extra}</MyObjectBuilder_CubeBlock>'
    )


def blueprint(name: str) -> str:
    blocks = [_block("CubeBlock", "LargeBlockArmorBlock", p) for p in FLOOR]
    for block, (pos, kind, subtype) in {**OWNERS, **TARGETS}.items():
        extra = f"<CustomName>{block}</CustomName>" + EXTRA.get(block, "")
        blocks.append(_block(kind, subtype, pos, extra, IDS[block], block in FACING_UP))
    return (
        '<?xml version="1.0"?><Definitions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<ShipBlueprints><ShipBlueprint xsi:type="MyObjectBuilder_ShipBlueprintDefinition">'
        f'<Id Type="MyObjectBuilder_ShipBlueprintDefinition" Subtype="{name}" />'
        "<CubeGrids><CubeGrid><GridSizeEnum>Large</GridSizeEnum><IsStatic>false</IsStatic>"
        '<PositionAndOrientation><Position x="0" y="0" z="0" />'
        '<Forward x="0" y="0" z="-1" /><Up x="0" y="1" z="0" /></PositionAndOrientation>'
        f"<CubeBlocks>{''.join(blocks)}</CubeBlocks><DisplayName>{name}</DisplayName>"
        "</CubeGrid></CubeGrids></ShipBlueprint></ShipBlueprints></Definitions>"
    )


class Game:
    """One test client: input, the fixture ship and the saved world"""

    def __init__(self, api: RemoteAPI):
        self.api = api
        self.grid = 0
        self.name = ""
        self.origin = (0.0, 0.0, 0.0)
        self.before: set[int] = set()
        self.pasted: list[int] = []
        self.aim_side = (0, 0, 1)

    # --- input ---------------------------------------------------------------

    def press(self, key: str, modifiers: list[str] | None = None) -> None:
        self.api.key(key, modifiers, hold_frames=1)
        time.sleep(0.3)

    def mouse(self, button: str, keys: list[str] | None = None) -> None:
        # The GUI click endpoint does not reach Sections' selection handler
        self.api.set_input_state(
            keys=keys, mode="override", **{f"mouse_{button}": True}
        )
        time.sleep(0.1)
        self.api.clear_input_state()
        time.sleep(0.5)

    def world(self, cell, grid: int | None = None) -> list[float]:
        world = self.api.call([CallOp.grid_to_world(grid or self.grid, cell)]).call(0)
        return [float(c) for c in world["world"]]

    def exists(self, cell, grid: int | None = None) -> bool:
        return self.api.call([CallOp.cube_exists(grid or self.grid, cell)]).call(0)[
            "exists"
        ]

    def look_from(self, eye, target) -> None:
        # A flying character keeps whatever roll it has, so place the feet below
        # the head along its own up vector. Turning changes that vector; repeat.
        for i in range(4):
            # float(): Remote sends small doubles as strings, se1/tickets/SE1-0109.md
            up = [float(u) for u in self.api.get_character()["up"]]
            self.api.character_teleport(*(e - 1.6 * u for e, u in zip(eye, up)))
            time.sleep(0.3)
            self.api.character_look_at(*target, tolerance=0.5)
            time.sleep(0.3)
            if i == 1:
                self.level()

    def level(self, screen_up=(0.0, 1.0, 0.0)) -> None:
        """Rolls the character (Q and E) until its up points along screen_up. An
        upside down character in space leaves the camera inside its own body, and
        the aim ray hits the character. Looking along screen_up, roll is free."""
        dot = lambda p, q: sum(x * y for x, y in zip(p, q))  # noqa: E731
        for _ in range(60):
            character = self.api.get_character()
            forward = [float(x) for x in character["forward"]]
            up = [float(x) for x in character["up"]]
            if abs(dot(forward, screen_up)) > 0.9:
                return
            want = [w - dot(screen_up, forward) * f for w, f in zip(screen_up, forward)]
            cross = [
                up[1] * want[2] - up[2] * want[1],
                up[2] * want[0] - up[0] * want[2],
                up[0] * want[1] - up[1] * want[0],
            ]
            angle = math.degrees(math.atan2(dot(cross, forward), dot(up, want)))
            if abs(angle) < 3:
                return
            # Q rolls about -80 degrees a second around the view axis, E the other way
            self.api.set_input_state(keys=["E" if angle > 0 else "Q"], mode="override")
            time.sleep(min(1.0, max(0.02, abs(angle) / 100)))
            self.api.clear_input_state()
            time.sleep(0.15)

    def axis(
        self, cell, side, grid: int | None = None
    ) -> tuple[list[float], list[float], float]:
        """World center of a cell, the unit vector of a grid axis, the cell size"""
        center = self.world(cell, grid)
        step = [
            a - b
            for a, b in zip(
                self.world(tuple(c + d for c, d in zip(cell, side)), grid), center
            )
        ]
        size = math.sqrt(sum(x * x for x in step))
        return center, [x / size for x in step], size

    def aim(
        self, cell, grid: int | None = None, side=(0, 0, 1), distance: float = 7
    ) -> dict:
        """Looks at a block from `distance` metres along a grid axis, +Z by default.
        A list of axes is tried in turn, for blocks that moving subgrids may hide."""
        for axis in side if isinstance(side, list) else [side]:
            target, direction, _ = self.axis(cell, axis, grid)
            eye = [t + distance * d for t, d in zip(target, direction)]
            self.look_from(eye, target)
            hit = self.api.get_character_target(15)
            block = hit.get("block") or {}
            if hit.get("hit") and tuple(block.get("min", ())) == tuple(cell):
                self.aim_side = axis
                return hit
        raise AssertionError((cell, hit))

    def leave_screens(self) -> None:
        self.press("Escape")
        if self.api.get_state()["paused"]:
            self.press("Escape")

    # --- Sections operations ---------------------------------------------------

    def select(self, first, second, grid=None, side=(0, 0, 1)) -> None:
        """Selects the box between two blocks and leaves the aim on the second one,
        which becomes the origin block of a copy"""
        self.aim(first, grid, side)
        self.press("NumPad0")
        self.mouse("left")
        self.aim(second, grid, side)
        self.mouse("left")

    # Ctrl inverts the "Include intersecting blocks" setting (off in the tests),
    # which takes in the 1x2x1 rotor stators of a one block high box
    # A copy or cut activates the clipboard a moment later. An Escape before
    # that would miss it, and the next click would paste.
    def cut(self, first, second, ctrl: bool = False, grid=None, side=(0, 0, 1)) -> None:
        self.select(first, second, grid, side)
        self.mouse("right", ["LeftControl"] if ctrl else None)
        time.sleep(1)

    def cut_block(self, cell, grid=None, side=(0, 0, 1)) -> None:
        """Cuts the aimed block alone (Delete while choosing the first corner)"""
        self.aim(cell, grid, side)
        self.press("NumPad0")
        self.press("Delete")
        time.sleep(1)

    def copy(self, first, second, ctrl: bool = False) -> None:
        self.select(first, second)
        self.mouse("left", ["LeftControl"] if ctrl else None)
        time.sleep(1)

    def delete(self, first, second, ctrl: bool = False) -> None:
        self.select(first, second)
        self.press("Back", ["LeftControl"] if ctrl else None)

    def paste_on(
        self,
        cell,
        grid: int | None = None,
        alt: bool = False,
        face=(0, 1, 0),
        distance: float = 6,
        toward=None,
    ) -> None:
        """Pastes the clipboard snapped to a grid: its origin block goes next to
        `cell`, on its `face` (+Y by default), looked at from `distance` metres.
        Alt disables the placement test, which takes the pasted section for a
        solid box. The clipboard stays active afterwards; leave it with Escape.

        The clipboard keeps the copy's orientation to the camera. Pass the grid
        axis the copy was aimed from as `toward`: the eye leans that way, so the
        camera faces the grid as it did when copying. By default it is the axis of
        the last aim, which is where the copy was made from."""
        center, direction, size = self.axis(cell, face, grid)
        _, lean, _ = self.axis(cell, toward or self.aim_side, grid)
        surface = [c + d * size / 2 for c, d in zip(center, direction)]
        eye = [p + distance * d + 0.3 * e for p, d, e in zip(surface, direction, lean)]
        self.look_from(eye, surface)
        if alt:
            # Sections reads Alt while the clipboard is active, before the click
            self.api.set_input_state(keys=["LeftAlt"], mode="override")
            time.sleep(0.3)
            self.api.set_input_state(keys=["LeftAlt"], mouse_left=True, mode="override")
            time.sleep(0.1)
            self.api.clear_input_state()
        else:
            self.api.click(*CENTER)
        time.sleep(1.5)
        self.leave_screens()

    def blueprint_to_clipboard(self, folder: str, title: str) -> None:
        """Loads a local blueprint into the clipboard through the Blueprints
        screen (F10): picks the folder, selects the blueprint, Copy to clipboard"""
        api = self.api
        self.press("F10")
        time.sleep(1.5)
        screen = len(api.list_screens()) - 1
        icons = [
            c
            for c in api.get_controls(screen)
            if c["type"] == "MyGuiControlButton"
            and c.get("visible")
            and not (c.get("properties") or {}).get("text")
        ]
        # Refresh, group, sort, new, directory, thumbnails, workshop
        api.control_click(name=icons[4]["name"], screen=screen)
        time.sleep(1.5)
        folders = len(api.list_screens()) - 1
        controls = api.get_controls(folders)
        path = next(c for c in controls if c["type"] == "MyGuiControlLabel")
        # The screen remembers the folder it showed last
        if not path["properties"]["text"].endswith("/" + folder):
            box = next(c for c in controls if c["type"] == "MyGuiControlListbox")
            row = [i["text"] for i in box["properties"]["items"]].index(folder)
            top = box["position"]["y"] - box["size"]["y"] / 2
            # Rows are 0.035 high; entering a folder takes a double click
            api.click(640, int((top + 0.025 + 0.035 * row) * 720), double=True)
            time.sleep(1)
        api.control_click(text="Open", screen=folders)
        time.sleep(1.5)

        def items():
            controls = api.get_controls(screen)
            return next(c for c in controls if c["type"] == "MyGuiControlList")[
                "children"
            ]

        # Clicks land on the wrong item further down the list; filter it to one
        search = next(
            c for c in api.get_controls(screen) if c["type"] == "MyGuiControlSearchBox"
        )
        api.control_set(search["name"], title, screen=screen)
        time.sleep(1.5)
        item = next(c for c in items() if c["properties"]["title"] == title)
        api.click(
            int((item["topLeft"]["x"] + item["size"]["x"] / 2) * 1280),
            int((item["topLeft"]["y"] + item["size"]["y"] / 2) * 720),
        )
        time.sleep(1)
        selected = [
            c["properties"]["title"] for c in items() if c["properties"]["selected"]
        ]
        assert selected == [title], selected
        api.control_click(text="Copy to clipboard", screen=screen)
        time.sleep(2)

    def paste_free(self) -> list[int]:
        """Pastes the clipboard into empty space above the fixture; returns the new grids"""
        before = {g["entityId"] for g in self.api.list_grids()}
        self.look_from(
            (self.origin[0], self.origin[1] + 60, self.origin[2] + 30),
            (self.origin[0], self.origin[1] + 60, self.origin[2] + 10),
        )
        self.api.click(*CENTER)
        time.sleep(1.5)
        self.leave_screens()
        return [
            g["entityId"] for g in self.api.list_grids() if g["entityId"] not in before
        ]

    # --- fixture ---------------------------------------------------------------

    def spawn(self, name: str, xml: str | None = None) -> int:
        """Pastes the fixture ship, or the blueprint in `xml`, at a place of its own,
        far from the world's grids"""
        api = self.api
        if api.get_state()["paused"]:
            self.press("Escape")
        if api.get_character().get("controlledEntity"):
            api.character_use()
            time.sleep(0.5)
        if not api.get_character()["jetpack"]:
            self.press("X")
        api.character_set_dampeners(True)
        n = next(_places) % 10000
        self.origin = (
            100000.0 + 100 * (n % 100),
            100000.0 + 100 * (n // 100),
            100000.0,
        )
        api.character_teleport(self.origin[0], self.origin[1] + 10, self.origin[2] + 30)
        time.sleep(0.5)
        self.name = name
        self.drop_clipboard()
        self.before = {g["entityId"] for g in api.list_grids()}
        self.pasted = [
            g["entityId"]
            for g in api.paste_blueprint(
                xml=xml or blueprint(name),
                position=self.origin,
                forward=(0, 0, -1),
                up=(0, 1, 0),
            )
        ]
        self.grid = self.pasted[0]
        time.sleep(1)
        if xml:
            return self.grid
        # The turret controller binds a rotor through its head's grid; the game
        # crashes binding one without a head (see test_turret_rotor_without_head)
        for rotor in ("Azimuth", "Elevation"):
            api.apply_action(self.grid, TARGETS[rotor][0], "AddRotorTopPart")
        time.sleep(1)
        return self.grid

    def spawn_blueprint(self, path: Path, name: str) -> list[int]:
        """Pastes a blueprint file at a place of its own; its first grid becomes
        self.grid. Returns all of its grids."""
        self.spawn(name, xml=path.read_text(encoding="utf-8"))
        return self.pasted

    def drop_clipboard(self) -> None:
        """Escape does not always reach a clipboard that a paste left active, and
        the next click would paste it. Click into empty space until nothing comes
        out, removing whatever does."""
        for _ in range(3):
            before = {g["entityId"] for g in self.api.list_grids()}
            self.api.click(*CENTER)
            time.sleep(1)
            pasted = [
                g["entityId"]
                for g in self.api.list_grids()
                if g["entityId"] not in before
            ]
            if not pasted:
                return
            for grid in pasted:
                self.api.close_grid(grid)
            self.leave_screens()
        raise AssertionError("The clipboard keeps pasting")

    def cleanup(self) -> None:
        """Removes every grid the test made: the ship, its rotor heads, the pastes"""
        for grid in self.api.list_grids():
            if grid["entityId"] not in self.before:
                self.api.close_grid(grid["entityId"])

    # --- the saved world -------------------------------------------------------

    def save(self) -> ET.Element:
        api = self.api
        path = Path(api.get_state()["path"])
        api.save()
        time.sleep(1)
        deadline = time.monotonic() + 120
        while api.get_state()["saving"]:
            assert time.monotonic() < deadline, "The save did not finish"
            time.sleep(0.5)
        return ET.parse(path / "SANDBOX_0_0_0_.sbs").getroot()

    def saved_grids(self, root: ET.Element | None = None) -> dict[int, ET.Element]:
        root = root if root is not None else self.save()
        return {
            int(g.findtext("EntityId")): g
            for g in root.iter("MyObjectBuilder_EntityBase")
            if g.get(XSI) == "MyObjectBuilder_CubeGrid"
            and int(g.findtext("EntityId")) not in self.before
        }


def storage(block: ET.Element) -> str | None:
    """The Sections block reference data of a saved block"""
    for item in block.iter("item"):
        if item.findtext("Key") == STORAGE_KEY:
            return item.findtext("Value")
    return None


def guid(block: ET.Element) -> str | None:
    data = storage(block)
    return data.split("\n", 1)[0].strip() if data else None


def blocks(grids) -> dict[str, ET.Element]:
    """Named blocks of saved grids; a name on several grids gets a #n suffix"""
    named: dict[str, ET.Element] = {}
    for grid in grids:
        for block in grid.find("CubeBlocks"):
            name = block.findtext("CustomName")
            if name:
                key, n = name, 1
                while key in named:
                    n += 1
                    key = f"{name} #{n}"
                named[key] = block
    return named


def references(grids) -> dict[str, dict]:
    """What each block of these grids refers to, by target name, for the blocks
    that refer to any. A reference to a block not on these grids reads as None.
    Only direct children are read: a projector holds whole projected grids."""
    named = blocks(grids)
    names = {block.findtext("EntityId"): name for name, block in named.items()}

    def name(entity_id):
        return names.get(entity_id) if entity_id not in (None, "0") else None

    def names_of(elements):
        # Selections and tool lists are sets, their order changes with a restore
        return sorted((name(x.text) for x in elements), key=str)

    components = "./ComponentContainer/Components/ComponentData/Component"
    result = {}
    for key, block in named.items():
        kind = block.get(XSI).replace("MyObjectBuilder_", "")
        refs = {}
        for slot in block.findall("./Toolbar/Slots/Slot"):
            target = slot.findtext("Data/BlockEntityId")
            if target:
                refs[f"slot {slot.findtext('Index')}"] = name(target)
        if block.find("SelectedBlocks") is not None:
            refs["selected"] = names_of(block.findall("SelectedBlocks/long"))
        if block.findtext("BindedCamera"):
            refs["camera"] = name(block.findtext("BindedCamera"))
        if kind == "TurretControlBlock":
            refs["azimuth"] = name(block.findtext("AzimuthId"))
            refs["elevation"] = name(block.findtext("ElevationId"))
            refs["camera"] = name(block.findtext("CameraId"))
            refs["tools"] = names_of(block.findall("ToolIds/long"))
        if kind == "OffensiveCombatBlock":
            # Each attack pattern keeps a weapon list; the selected one is filled
            weapons = [
                w for w in block.findall(f"{components}/SelectedWeapons") if len(w)
            ]
            if weapons:
                refs["weapons"] = names_of(weapons[0])
        if kind == "PathRecorderBlock":
            waypoints = block.findall(
                f"{components}/Waypoints/MyObjectBuilder_AutopilotWaypoint"
            )
            for i, waypoint in enumerate(waypoints):
                refs[f"waypoint {i}"] = [
                    name(item.findtext("BlockEntityId"))
                    for item in waypoint.findall("Actions/MyObjectBuilder_ToolbarItem")
                ]
        if kind == "ButtonPanel":
            items = block.findall("./CustomButtonNames/dictionary/item")
            if items:
                refs["button names"] = sorted(
                    f"{i.findtext('Key')}:{i.findtext('Value')}" for i in items
                )
        if refs:
            result[key] = refs
    return result


def broken(refs: dict[str, dict]) -> dict[str, list[str]]:
    """The references of each owner that point at no block of the grids"""
    result = {}
    for owner, items in refs.items():
        bad = [
            k
            for k, v in items.items()
            if v is None or (isinstance(v, list) and None in v)
        ]
        if bad:
            result[owner] = bad
    return result


# Turret controllers: their toolbar is not backed up, and restored tools come on
# top of the stale ones. The fixture's own tests track that (TURRET_TICKET).
TURRET_TICKET = "se1/tickets/SE1-0106.md"


def without_turret_gaps(refs: dict[str, dict]) -> dict[str, dict]:
    def gap(items, key):
        return "azimuth" in items and (key == "tools" or key.startswith("slot"))

    return {
        owner: {k: v for k, v in items.items() if not gap(items, k)}
        for owner, items in refs.items()
    }
