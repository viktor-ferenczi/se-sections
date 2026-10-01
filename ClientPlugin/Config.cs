using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Xml.Serialization;
using ClientPlugin.Settings;
using ClientPlugin.Settings.Elements;
using VRage.Input;
using VRage.Utils;
using VRageMath;

namespace ClientPlugin
{
    public class Config : INotifyPropertyChanged
    {
        #region Options

        private bool deleteConfirmation = true;
        private bool cutConfirmation = true;

        private string sectionsSubdirectory = "Sections";
        private bool renameBlueprint = true;

        private bool fixPastePosition = true;
        private bool handleSubgrids = true;
        private bool disablePlacementTest = true;
        private bool restoreToolbars = true;
        private bool includeIntersectingBlocks;
        private float hiddenBlockOpacity = 50f;
        private float hiddenBlockSaturation = 50f;
        private float autoHideRadius = 7.5f;
        private bool autoHideBlocks;

        private bool showHints = true;
        private bool showSize = true;
        private float textPosition = 0.70f;
        private float sizeTextScale = 2f;
        private Color hintColor = new Color(0xdd, 0xdd, 0);
        private Color sizeColor = new Color(0xff, 0x99, 0);
        private int textShadowOffset = 2;
        private Color textShadowColor = new Color(0, 0, 0, 0xcc);

        private int highlightDensity = 3;
        private Color firstColor = Color.Blue;
        private Color secondColor = Color.Green;
        private Color aimedColor = Color.Blue;
        private Color boxColor = Color.Cyan;
        private Color finalBoxColor = Color.Yellow;

        private Binding activate = new Binding(MyKeys.NumPad0);
        private Binding resetSelection = new Binding(MyKeys.R);
        private Binding saveSelectedBlocks = new Binding(MyKeys.Enter);
        private Binding deleteSelectedBlocks = new Binding(MyKeys.Back);
        private Binding clearBlockReferenceData = new Binding(MyKeys.OemMinus);
        private Binding hideSelectedBlocks = new Binding(MyKeys.H);
        private Binding showSelectedBlocks = new Binding(MyKeys.H, shift: true);
        private Binding restoreGridCutaway = new Binding(MyKeys.H, alt: true);
        private Binding restoreAllCutaways = new Binding(MyKeys.H, ctrl: true, alt: true);

        private Binding toggleAutoHide = new Binding(MyKeys.OemPipe, ctrl: true, alt: true);
        private Binding decreaseAutoHideRadius = new Binding(
            MyKeys.OemOpenBrackets,
            ctrl: true,
            alt: true
        );
        private Binding increaseAutoHideRadius = new Binding(
            MyKeys.OemCloseBrackets,
            ctrl: true,
            alt: true
        );

        // Not configurable yet
        public readonly MyStringId BlockMaterial = MyStringId.GetOrCompute(
            "ContainerBorderSelected"
        );
        public readonly MyStringId BoxMaterial = MyStringId.GetOrCompute("ContainerBorderSelected");

        #endregion

        #region User interface

        public readonly string Title = "Sections";

        [Separator("Confirmations")]
        [Checkbox(
            description: "Ask for confirmation before deleting the selected blocks (Backspace)"
        )]
        public bool DeleteConfirmation
        {
            get => deleteConfirmation;
            set => SetField(ref deleteConfirmation, value);
        }

        [Checkbox(description: "Ask for confirmation before cutting the selected blocks (RMB)")]
        public bool CutConfirmation
        {
            get => cutConfirmation;
            set => SetField(ref cutConfirmation, value);
        }

        [Separator("Blueprints")]
        [Textbox(description: "Name of the blueprint subdirectory to store the sections to")]
        public string SectionsSubdirectory
        {
            get => sectionsSubdirectory;
            set => SetField(ref sectionsSubdirectory, value);
        }

        [Checkbox(
            description: "Opens a dialog box to rename the blueprint on saving and confirm overwrite (disables automatic numbering)"
        )]
        public bool RenameBlueprint
        {
            get => renameBlueprint;
            set => SetField(ref renameBlueprint, value);
        }

        [Separator("Features")]
        [Checkbox(
            description: "Change the drag position on pasting grids, so you can point directly where the origin block should go"
        )]
        public bool FixPastePosition
        {
            get => fixPastePosition;
            set => SetField(ref fixPastePosition, value);
        }

        [Checkbox(
            label: "Include intersecting blocks",
            description: "Include whole blocks whose grid-aligned bounding boxes overlap the selection; Ctrl inverts this for cutaway, cut, copy, delete, and blueprint operations"
        )]
        public bool IncludeIntersectingBlocks
        {
            get => includeIntersectingBlocks;
            set => SetField(ref includeIntersectingBlocks, value);
        }

        [Slider(
            0f,
            100f,
            1f,
            label: "Hidden block opacity (%)",
            description: "Opacity of blocks in a cutaway; zero makes them invisible"
        )]
        public float HiddenBlockOpacity
        {
            get => hiddenBlockOpacity;
            set => SetField(ref hiddenBlockOpacity, MathHelper.Clamp(value, 0f, 100f));
        }

        [Slider(
            0f,
            100f,
            1f,
            label: "Hidden block saturation (%)",
            description: "Saturation multiplier for cutaway blocks; zero makes them gray"
        )]
        public float HiddenBlockSaturation
        {
            get => hiddenBlockSaturation;
            set => SetField(ref hiddenBlockSaturation, MathHelper.Clamp(value, 0f, 100f));
        }

        [Checkbox(
            description: "Handle subgrids together with mechanical connection blocks (the ones which would be disconnected)"
        )]
        public bool HandleSubgrids
        {
            get => handleSubgrids;
            set => SetField(ref handleSubgrids, value);
        }

        [Checkbox(
            description: "Holding Alt disables the placement test while pasting, use this only with great care"
        )]
        public bool DisablePlacementTest
        {
            get => disablePlacementTest;
            set => SetField(ref disablePlacementTest, value);
        }

        [Checkbox(
            description: "Backup and restore associated blocks (toolbar slots, event and turret controllers)"
        )]
        public bool RestoreToolbars
        {
            get => restoreToolbars;
            set => SetField(ref restoreToolbars, value);
        }

        [Separator("Auto-hide")]
        [XmlIgnore]
        [Checkbox(
            label: "Auto-hide blocks",
            description: "Temporarily hide blocks touching a sphere around the character; requires cutaway permission"
        )]
        public bool AutoHideBlocks
        {
            get => autoHideBlocks;
            set => SetField(ref autoHideBlocks, Logic.Cutaway.SetAutoHide(value));
        }

        internal void StopAutoHide() =>
            SetField(ref autoHideBlocks, Logic.Cutaway.SetAutoHide(false, force: true));

        [Slider(
            0f,
            50f,
            0.1f,
            label: "Auto-hide radius (m)",
            description: "Default radius loaded each time auto-hide is enabled; from 0 to 50 meters in 0.1 meter steps. Hotkeys temporarily adjust the active radius."
        )]
        public float AutoHideRadius
        {
            get => autoHideRadius;
            set =>
                SetField(
                    ref autoHideRadius,
                    (float)System.Math.Round(MathHelper.Clamp(value, 0f, 50f), 1)
                );
        }

        [Keybind(description: "Toggle auto-hide blocks")]
        public Binding ToggleAutoHide
        {
            get => toggleAutoHide;
            set => SetField(ref toggleAutoHide, value);
        }

        [Keybind(description: "Decrease auto-hide radius by 0.1 meter")]
        public Binding DecreaseAutoHideRadius
        {
            get => decreaseAutoHideRadius;
            set => SetField(ref decreaseAutoHideRadius, value);
        }

        [Keybind(description: "Increase auto-hide radius by 0.1 meter")]
        public Binding IncreaseAutoHideRadius
        {
            get => increaseAutoHideRadius;
            set => SetField(ref increaseAutoHideRadius, value);
        }

        [Separator("Overlay")]
        [Checkbox(description: "Enable showing the hints on screen")]
        public bool ShowHints
        {
            get => showHints;
            set => SetField(ref showHints, value);
        }

        [Checkbox(description: "Enable showing the size of the selection box on screen")]
        public bool ShowSize
        {
            get => showSize;
            set => SetField(ref showSize, value);
        }

        [Slider(
            0f,
            0.9f,
            0.01f,
            description: "Vertical position of the box size and hints on the screen"
        )]
        public float TextPosition
        {
            get => textPosition;
            set => SetField(ref textPosition, value);
        }

        [Slider(0.1f, 10f, 0.01f, description: "Font scale for the box size")]
        public float SizeTextScale
        {
            get => sizeTextScale;
            set => SetField(ref sizeTextScale, value);
        }

        [Color(description: "Hint text color")]
        public Color HintColor
        {
            get => hintColor;
            set => SetField(ref hintColor, value);
        }

        [Color(description: "Box size text color")]
        public Color SizeColor
        {
            get => sizeColor;
            set => SetField(ref sizeColor, value);
        }

        [Slider(
            0f,
            10f,
            1f,
            SliderAttribute.SliderType.Integer,
            description: "Text shadow offset (set to zero to turn off text shadows)"
        )]
        public int TextShadowOffset
        {
            get => textShadowOffset;
            set => SetField(ref textShadowOffset, value);
        }

        [Color(hasAlpha: true, description: "Text shadow color")]
        public Color TextShadowColor
        {
            get => textShadowColor;
            set => SetField(ref textShadowColor, value);
        }

        [Separator("Block Selection")]
        [Slider(
            1f,
            10f,
            1f,
            SliderAttribute.SliderType.Integer,
            description: "Density of the highlights (number of overdraws)"
        )]
        public int HighlightDensity
        {
            get => highlightDensity;
            set => SetField(ref highlightDensity, value);
        }

        [Color(description: "Highlight color of the first selected block")]
        public Color FirstColor
        {
            get => firstColor;
            set => SetField(ref firstColor, value);
        }

        [Color(description: "Highlight color of the second selected block")]
        public Color SecondColor
        {
            get => secondColor;
            set => SetField(ref secondColor, value);
        }

        [Color(description: "Highlight color of the aimed block for blueprinting")]
        public Color AimedColor
        {
            get => aimedColor;
            set => SetField(ref aimedColor, value);
        }

        [Color(description: "Highlight color of the selection box while picking the second block")]
        public Color BoxColor
        {
            get => boxColor;
            set => SetField(ref boxColor, value);
        }

        [Color(description: "Highlight color of the final selection box")]
        public Color FinalBoxColor
        {
            get => finalBoxColor;
            set => SetField(ref finalBoxColor, value);
        }

        [Separator("Keys")]
        [Keybind(description: "Activate box selection")]
        public Binding Activate
        {
            get => activate;
            set => SetField(ref activate, value);
        }

        [Keybind(description: "Reset the selection box to its original extents")]
        public Binding ResetSelection
        {
            get => resetSelection;
            set => SetField(ref resetSelection, value);
        }

        [Keybind(description: "Save selected blocks as a section blueprint")]
        public Binding SaveSelectedBlocks
        {
            get => saveSelectedBlocks;
            set => SetField(ref saveSelectedBlocks, value);
        }

        [Keybind(description: "Delete selected blocks (with confirmation by default)")]
        public Binding DeleteSelectedBlocks
        {
            get => deleteSelectedBlocks;
            set => SetField(ref deleteSelectedBlocks, value);
        }

        [Keybind(description: "Clear block reference data")]
        public Binding ClearBlockReferenceData
        {
            get => clearBlockReferenceData;
            set => SetField(ref clearBlockReferenceData, value);
        }

        [Keybind(
            description: "Add selected blocks to the grid's cutaway mask; Ctrl inverts Include intersecting blocks"
        )]
        public Binding HideSelectedBlocks
        {
            get => hideSelectedBlocks;
            set => SetField(ref hideSelectedBlocks, value);
        }

        [Keybind(
            description: "Remove selected blocks from the grid's cutaway mask; Ctrl inverts Include intersecting blocks"
        )]
        public Binding ShowSelectedBlocks
        {
            get => showSelectedBlocks;
            set => SetField(ref showSelectedBlocks, value);
        }

        [Keybind(description: "Reset the selected or aimed grid to all visible")]
        public Binding RestoreGridCutaway
        {
            get => restoreGridCutaway;
            set => SetField(ref restoreGridCutaway, value);
        }

        [Button(
            label: "Show all blocks on all grids",
            description: "Reset every cutaway, including entirely hidden grids"
        )]
        public System.Action ShowAllBlocks =>
            () =>
            {
                Logic.Cutaway.Restore();
                Plugin.Instance.RefreshConfigDialog();
            };

        [Keybind(
            description: "Restore all hidden sections, including grids that are entirely hidden"
        )]
        public Binding RestoreAllCutaways
        {
            get => restoreAllCutaways;
            set => SetField(ref restoreAllCutaways, value);
        }

        #endregion

        #region Property change notification bilerplate

        public static readonly Config Default = new Config();
        public static readonly Config Current = ConfigStorage.Load();

        public event PropertyChangedEventHandler PropertyChanged;

        protected virtual void OnPropertyChanged(string propertyName)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
        }

        private bool SetField<T>(
            ref T field,
            T value,
            [CallerMemberName] string propertyName = null
        )
        {
            if (EqualityComparer<T>.Default.Equals(field, value))
                return false;
            field = value;
            OnPropertyChanged(propertyName);
            return true;
        }

        #endregion
    }
}
