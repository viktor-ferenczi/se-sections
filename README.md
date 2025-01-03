# Sections

**Sections** is a **Space Engineers plugin**, which allows for **selecting part of a grid**, then copying, cutting, deleting or blueprinting the blocks inside the selection box.

**This is an implementation of a publicly announced Space Engineers 2 feature** for the current version of the game. It is so useful, that I could not stand not implementing it. Sorry. :)

[![Watch the video](doc/Thumbnail.png)](https://www.youtube.com/watch?v=W0S-wIaIZ80)

This is an implementation of a publicly announced Space Engineers 2 feature
for the current version of the game. It is so useful, that I could not stand
not implementing it. Sorry. :)

For support please [join the SE Mods Discord](https://discord.gg/PYPFPGf3Ca).

Please consider supporting my work on [Patreon](https://www.patreon.com/semods) or one time via [PayPal](https://www.paypal.com/paypalme/vferenczi/).

*Thank you and enjoy!*

## Prerequisites

- [Space Engineers](https://store.steampowered.com/app/244850/Space_Engineers/)
- [Plugin Loader](https://github.com/sepluginloader/SpaceEngineersLauncher)

## Installation

1. Install Plugin Loader's [Space Engineers Launcher](https://github.com/sepluginloader/SpaceEngineersLauncher)
2. Run the game
3. In the new **Plugins** menu add the **Sections** plugin
4. Apply and restart the game as requested

## Features

- [Demo Video](https://www.youtube.com/watch?v=W0S-wIaIZ80)
- [Test World](https://steamcommunity.com/sharedfiles/filedetails/?id=3386716105)

This plugin is designed for offline ship design. It works only in creative mode.
It is availabel in survival mode only if the creative mode tools are enabled for the player.

### Selecting grid sections

Start your selection by pressing the **NumPad 0** key. It is rebindable in the configuration,
should you play on a keyboard without a numpad.

Follow the hints shown on the screen. You do **not** need to hold a block in hand
for the selection to work, actually it would just be in the way. I suggest pressing
`0` to deselect anything held in hand to clear up your view.

![Selecting the first block](doc/Selecting1.png "Selecting the first block")
![Selecting the second block](doc/Selecting2.png "Selecting the second block")

The block distance from the character is the same as normal block placement in creative mode.
You can change the maximum distance of the aimed block by keeping any block at hand while
Sections is **not** active and using the `Ctrl-MouseWheel` to change the distance. 

### Resizing the selection box

Adjust the selection box as needed:
- **Block rotation keys**: Grow the selection box. Hold down **shift** to **shrink**.
- **R key**: Resets the selection box to its initial size.

![Resizing the selection box](doc/Resizing.png "Resizing the selection box")

You are free to fly around while right-sizing the selection box.
It is helpful, since you will likely need to check the other side
or inside your ship as well.

The keys used here are different from  the ones seen in the SE2 reveal video
in order to allow for flying around while resizing the selection box.

### Section operations

Once the selection is good, you can do these operations on the selected blocks:
- **Left mouse button**: Copy the section to the clipboard, so it can be pasted elsewhere.
- **Right mouse button**: Cut the section (copy, then delete), so it can be moved elsewhere.
- **Backspace key**: Delete the blocks in the section. It may result in a grid split, so careful.
- **Enter key**: Make a blueprint out of the blocks inside the section. They will be stored locally in the `Sections` blueprint folder. You can name the blueprint on saving and confirm a possible overwrite.

By default, only the blocks fully enclosed in the selection box are operated on.

You can hold down the **Ctrl** key while using the above section operations to include
the blocks intersecting the surface of the selection box without being fully contained.

### Subgrid support

Any **subgrids** which would be orphaned if the selected blocks would be deleted are copied
together with the section. This allows for cutting out custom PDCs and other mechanical
constructs using subgrids without disconnecting the mechanical bases from their tops,
so they can also be pasted back into the same grid.

Notice how the custom PDCs were cut out together with their base:
![PDC cut out](doc/PDCCutOut.png "PDC cut out")

The same applies to saving to a section blueprint:
![PDC selection](doc/PDC-Selection.png "PDC selection")

Pasted the blueprint into clear space. As you can see both PDCs are preserved:
![PDC pasted](doc/PDC-Pasted.png "PDC pasted")

Please note, that the selection box must cover only the mechanical base or top blocks
connecting the subgrids. The selection box does **not** have to cover the subgrids
themselves, because the selection applies only to blocks on the same grid as the
first selected block.

Any subgraph of subgrids are also copied the same way, as long as they lose all
mechanical connections to the main grid which was selected. It ensures that no subgrid
is lost. It should work in any combination of mechanical connections, including reverse
order ones (which cannot be built directly in the game, only "towed" together) and
multiple connections between the same pair of subgrids (like double hinged PDCs or doors).

### Preserving block references

References between blocks via toolbars, drop-down block selectors or block lists would
be lost if part of the grid is cut or copied via a section blueprint. To avoid this from
happening the Sections plugin implements a mechanism to store all such block references
and restore them relationships when grids are pasted back onto each other. For example
slicing a ship and merging the pieces back together should not break functionality.

The following blocks refer to other blocks:
- Any block with a toolbar (`Cockpit`, `Sensor`, `AI Defensive`, etc.) 
- `Remote Control` assigned camera 
- `Event Controller` selected blocks 
- `Turret Controller` azimuth and elevation rotors, camera and bound tool blocks
- `AI Offensive` block weapons list
- `AI Recorder` block waypoint toolbars

For each terminal block the Sections plugin saves the following into a new entry in `ModStorage`:
- GUID of the block itself
- GUIDs of each block referenced

This data is saved right before the Sections plugin operates on a grid.

You can see the data stored by using the `Block Reference Data` button on the block's terminal.

For example the toolbar slots of a `Cockpit` saved like this: 
![Block reference data](doc/BlockReferenceData.png "Block reference data")

This information is copied with the grid, saved with the world and blueprints. This information
is then used to restore any missing block references whenever the grids with such data stored
are pasted onto each other. These are typically ship "slices" produced by this plugin.

Should you need it, this information can be cleared from the grid. Activate the Sections
plugin (NumPad 0), face a grid and press the `-` (minus) key to initiate the clearing of
this data. Please note that these keys are remappable. This operation has a confirmation
dialog which cannot be turned off. The clearing affects only the faced grid and all of 
its subgrids.

### Managing saved sections

You can paste your saved sections efficiently using the existing blueprint functionality.

Configure the Blueprints dialog (F10) this way:
- Select only the Home source for blueprints, so it lists only local files
- Open the `Sections` folder: Click on the folder icon above the search box, then double-click on `Sections`

This way you can press F10 and quick search immediately in the saved sections.

The `Sections` folder will be created automatically when you save your first section.

The sections are saved with the grid names, plus numbering to avoid overwriting.
The numbering works exactly the same way as saving blueprints with Ctrl-B.

The sections have thumbnails generated from a screenshot taken when the section
is saved. Position your character to have a good view before saving the section,
if possible. If not, then you can make a new screenshot in the Blueprints dialog.
![Blueprints dialog](doc/BlueprintsDialog.png "Blueprints dialog")

### Pasting sections

The vanilla game sets the drag point of pasted blueprints to the center of their bounding sphere.
Not to mention, this is very suboptimal for sections, because it works well only if you try to
align a block near the center of the blueprint.

For example, let's consider this corner girder section. 
Notice the blue cube at the far corner, that's the origin block faced while making the blueprint.
That's why it is at the dead center of the blueprint's thumbnail:
![Corner girder section](doc/CornerGirderSection.png "Corner girder section")

If you're trying to paste it on top of the other corner in the vanilla game, 
then it is impossible to align properly:
![Unable to align](doc/UnableToAlign.png "Unable to align")

With the fix implemented in this plugin you can just face where the origin block should go:
![Able to align](doc/AbleToAlign.png "Unable to align")

Certainly you have to make sure first, that the rotation is right, but that's already second nature...

### Disabling the placement test

**Holding Alt disables the placement test** while pasting. It is very useful if there is a subgrid
in the way and while you know for sure it will not collide the game does not agree with you.

It happens with some tight designs. For example if a small block torpedo is inside a tube of
large block sliding doors:
![Disable placement test](doc/DisablePlacementTest-1.png "Disable placement test")

Let's cut out the PDC block and the torpedo tubes, so there is easy access to the torpedo welders:
![Disable placement test](doc/DisablePlacementTest-2.png "Disable placement test")
![Disable placement test](doc/DisablePlacementTest-3.png "Disable placement test")

When you attempt to paste the block back the game shows a red placement box, indicating a collision:
![Disable placement test](doc/DisablePlacementTest-4.png "Disable placement test")

**Hold down Alt in this state.** It will show a warning message to remind you and
the placement box will turn green, so the block can be pasted. 

**Use this feature with great care!** Always make sure that no actual collision will happen,
otherwise you will likely trigger Clang.

## Configuration

Press `Ctrl-Alt-/` while in-game and not in the GUI. It will open the list of
configurable plugins. Select **Sections** from the list to configure this plugin.
Alternatively you can open the settings by double-clicking on this plugin in the Plugins
dialog of Plugin Loader, then clicking **Settings** in the dialog opened.
The configuration can be changed anytime without having to restart the game.

![Configuration](doc/ConfigDialog.png "Config Dialog")

## Known issues and limitations

- **No support for symmetry mode.** This is planned for version 1.4.0.
- Pasting sections with disconnected blocks works as expected, but may result in "floating" blocks. This is normal and by design to allow for some building tricks. **Play with it!**
- This plugin is **largely untested in survival** (only with creative mode tools enabled) and is disabled in multiplayer (even if you're an admin). It should work if you're playing on the server of a "Friends" multiplayer game, but this mode has **not** been tested yet.

## Troubleshooting

Should you have any issues using this plugin, then please either submit a ticket here
on GitHub or report the issue in the `#bug-reports` channel of the [SE Mods Discord](https://discord.gg/PYPFPGf3Ca).

## Legal

Space Engineers and Space Engineers 2 are trademarks of Keen Software House s.r.o.

## Want to know more?

- [SE Mods Discord](https://discord.gg/PYPFPGf3Ca) FAQ, Troubleshooting, Support, Bug Reports, Discussion
- [Plugin Loader Discord](https://discord.gg/6ETGRU3CzR) Everything about plugins
- [YouTube Channel](https://www.youtube.com/channel/UCc5ar3cW9qoOgdBb1FM_rxQ)
- [Source code](https://github.com/viktor-ferenczi/se-sections)
- [Bug reports](https://discord.gg/x3Z8Ug5YkQ)

## Credits

### Workshop

This is the ship used in some documentation screenshots and demo videos:
[IMDC Honorius DDS Warship](https://steamcommunity.com/sharedfiles/filedetails/?id=1734992253)

![IMDC Honorius DDS Warship](doc/IMDC-Honorius-Warship.jpg "IMDC Honorius DDS Warship")

### Code contributors
- Klime: How to disable the clipboard placement test (`BuildFreedom` plugin)
- Pas2704: Mod storage data component registration code

### Patreon Supporters

_in alphabetical order_

#### Admiral level
- BetaMark
- Casinost
- Mordith - Guardians SE
- Robot10
- wafoxxx

#### Captain level
- Diggz
- jiringgot
- Jimbo
- Kam Solastor
- lazul
- Linux123123
- Lotan
- Lurking StarCpt
- NeonDrip
- NeVaR
- opesoorry

#### Testers
- Avaness
- mkaito

### Creators
- avaness - Plugin Loader
- Fred XVI - Racing maps
- Kamikaze - M&M mod
- LTP
- Mordith - Guardians SE
- Mike Dude - Guardians SE
- SwiftyTech - Stargate Dimensions

**Thank you very much for all your support!**