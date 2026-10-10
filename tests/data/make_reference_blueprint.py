"""Builds block-reference-test.sbc from Viktor's manual test world.

The world "Sections Block Reference Test" holds two copies of a mechanical group:
a static large grid, a small grid on its advanced rotor, and two hinge arms with
solar panels on that. This takes the copy at x < -80, names the terminal blocks
that have no name (the tests key blocks by name), and adds what the world lacks:
timer, sensor and defensive combat blocks on both grid sizes, and toolbar slots
and a button name on the small button panel. Their references cross grids.

    python tests/data/make_reference_blueprint.py <world folder>
"""

import copy
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

XSI = "{http://www.w3.org/2001/XMLSchema-instance}type"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
ET.register_namespace("xsi", XSI_NS)
OUT = Path(__file__).with_name("block-reference-test.sbc")
LARGE, SMALL = "112045162718899088", "120843266232763296"

NAMES = {
    "73636127674209501": "Offensive SG",
    "137669237176876306": "AI Recorder SG",
    "88360252355767354": "Button Panel SG",
    "135320405563807517": "Control Panel SG",
    "120368627260239628": "LCD LG",
    "110326395269237460": "Battery 2 LG",
    "80196669405180812": "Solar Panel Solar 1",
    "77933309357409603": "Control Panel Solar 1",
    "112814251145103209": "Solar Panel Solar 2",
    "133300086356386255": "Control Panel Solar 2",
}
# Rotating lights (DLC) to timer blocks: entity id to subtype and new name
REPLACED = {
    "127219565499984404": ("TimerBlockLarge", "Target Timer LG"),
    "73040222908095014": ("TimerBlockSmall", "Target Timer SG"),
}
IDS = {
    "Target Timer LG": "127219565499984404",
    "Target Timer SG": "73040222908095014",
    "Event Controller LG": "125615910747572188",
    "Battery": "106794945896805135",
    "Rotor Solar 2": "93624901353270639",
    "Camera RC LG": "129479133920390725",
    "Camera Solar 2": "93873568301231741",
    "Gatling Gun Solar 1a": "113800258097603200",
    "Gatling Gun Solar 2a": "129821660155885674",
    "Gatling Gun 1a SG": "136916029158710285",
}


def slots(*items):
    return "".join(
        f'<Slot><Index>{i}</Index><Item /><Data xsi:type="MyObjectBuilder_ToolbarItemTerminalBlock">'
        f"<Action>{action}</Action><BlockEntityId>{IDS[target]}</BlockEntityId></Data></Slot>"
        for i, (target, action) in enumerate(items)
    )


def toolbar(*items):
    return f'<Toolbar><ToolbarType>Character</ToolbarType><SelectedSlot xsi:nil="true" /><Slots>{slots(*items)}</Slots></Toolbar>'


# Under the decks: large grid y -1 below its deck at y 0, small grid y 1 below
# its deck at y 2. Sensors mount on their back only, which faces the deck.
ADDED = {
    LARGE: [
        (
            "TimerBlock",
            "TimerBlockLarge",
            (1, -1, 1),
            "Timer LG",
            "Forward",
            "Up",
            toolbar(
                ("Gatling Gun Solar 1a", "OnOff"),
                ("Rotor Solar 2", "OnOff"),
                ("Battery", "OnOff"),
            )
            + "<Delay>3000</Delay>",
        ),
        (
            "SensorBlock",
            "LargeBlockSensor",
            (3, -1, 1),
            "Sensor LG",
            "Down",
            "Forward",
            toolbar(("Target Timer SG", "OnOff"))
            + "<DetectPlayers>false</DetectPlayers>",
        ),
        (
            "DefensiveCombatBlock",
            "LargeDefensiveCombat",
            (5, -1, 1),
            "Defensive LG",
            "Forward",
            "Up",
            toolbar(("Camera RC LG", "View")),
        ),
    ],
    SMALL: [
        (
            "TimerBlock",
            "TimerBlockSmall",
            (-5, 1, 1),
            "Timer SG",
            "Forward",
            "Up",
            toolbar(("Target Timer LG", "OnOff"), ("Camera Solar 2", "View"))
            + "<Delay>3000</Delay>",
        ),
        (
            "SensorBlock",
            "SmallBlockSensor",
            (-7, 1, 1),
            "Sensor SG",
            "Down",
            "Forward",
            toolbar(("Event Controller LG", "OnOff"))
            + "<DetectPlayers>false</DetectPlayers>",
        ),
        (
            "DefensiveCombatBlock",
            "SmallDefensiveCombat",
            (-9, 1, 1),
            "Defensive SG",
            "Forward",
            "Up",
            toolbar(("Gatling Gun Solar 2a", "OnOff")),
        ),
    ],
}
# The small button panel has a single button
BUTTONS = toolbar(("Target Timer LG", "OnOff"))
BUTTON_NAMES = "<CustomButtonNames><dictionary><item><Key>0</Key><Value>Target LG</Value></item></dictionary></CustomButtonNames>"


def element(xml):
    return ET.fromstring(f'<root xmlns:xsi="{XSI_NS}">{xml}</root>')[0]


def main(world: Path):
    root = ET.parse(world / "SANDBOX_0_0_0_.sbs").getroot()
    grids = [
        g
        for g in root.iter("MyObjectBuilder_EntityBase")
        if g.get(XSI) == "MyObjectBuilder_CubeGrid"
        and float(g.find("PositionAndOrientation/Position").get("x")) < -80
    ]
    # The large grid first: it is the one the paste places
    grids.sort(key=lambda g: g.findtext("EntityId") != LARGE)
    out_grids = []
    for g in grids:
        grid = ET.Element("CubeGrid")
        for child in g:
            grid.append(copy.deepcopy(child))
        blocks = grid.find("CubeBlocks")
        for block in list(blocks):
            if block.findtext("EntityId") in REPLACED:
                subtype, name = REPLACED[block.findtext("EntityId")]
                keep = "".join(
                    ET.tostring(block.find(tag), encoding="unicode")
                    for tag in (
                        "EntityId",
                        "Min",
                        "BlockOrientation",
                        "ColorMaskHSV",
                        "Owner",
                        "BuiltBy",
                        "ShareMode",
                    )
                    if block.find(tag) is not None
                )
                timer = element(
                    f'<MyObjectBuilder_CubeBlock xsi:type="MyObjectBuilder_TimerBlock"><SubtypeName>{subtype}</SubtypeName>'
                    f"{keep}<CustomName>{name}</CustomName>{toolbar()}<Delay>3000</Delay></MyObjectBuilder_CubeBlock>"
                )
                blocks.insert(list(blocks).index(block), timer)
                blocks.remove(block)
                continue
            name = NAMES.get(block.findtext("EntityId"))
            if name:
                custom = block.find("CustomName")
                if custom is None:
                    custom = ET.SubElement(block, "CustomName")
                custom.text = name
            if block.findtext("EntityId") == "88360252355767354":
                block.remove(block.find("Toolbar"))
                block.remove(block.find("CustomButtonNames"))
                block.append(element(BUTTONS))
                block.append(element(BUTTON_NAMES))
        for n, (kind, subtype, (x, y, z), name, forward, up, extra) in enumerate(
            ADDED.get(g.findtext("EntityId"), [])
        ):
            blocks.append(
                element(
                    f'<MyObjectBuilder_CubeBlock xsi:type="MyObjectBuilder_{kind}"><SubtypeName>{subtype}</SubtypeName>'
                    f"<EntityId>{900000000000301 + n + (10 if g.findtext('EntityId') == SMALL else 0)}</EntityId>"
                    f'<Min x="{x}" y="{y}" z="{z}" /><BlockOrientation Forward="{forward}" Up="{up}" />'
                    f"<CustomName>{name}</CustomName>{extra}</MyObjectBuilder_CubeBlock>"
                )
            )
        out_grids.append(grid)
    definitions = ET.fromstring(
        f'<Definitions xmlns:xsi="{XSI_NS}"><ShipBlueprints>'
        '<ShipBlueprint xsi:type="MyObjectBuilder_ShipBlueprintDefinition">'
        '<Id Type="MyObjectBuilder_ShipBlueprintDefinition" Subtype="Sections Block Reference Test" />'
        "<CubeGrids /></ShipBlueprint></ShipBlueprints></Definitions>"
    )
    definitions.find(".//CubeGrids").extend(out_grids)
    ET.ElementTree(definitions).write(OUT, encoding="utf-8", xml_declaration=True)
    print(
        f"{OUT}: {len(out_grids)} grids, {sum(len(g.find('CubeBlocks')) for g in out_grids)} blocks"
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
