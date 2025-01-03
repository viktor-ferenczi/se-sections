using ClientPlugin.Settings;
using ClientPlugin.Settings.Elements;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.CompilerServices;
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

        // Not configurable yet
        public readonly MyStringId BlockMaterial = MyStringId.GetOrCompute("ContainerBorderSelected");
        public readonly MyStringId BoxMaterial = MyStringId.GetOrCompute("ContainerBorderSelected");

        #endregion

        #region User interface

        public readonly string Title = "Sections";

        [Separator("Confirmations")]
        [Checkbox(description: "Ask for confirmation before deleting the selected blocks (Backspace)")]
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

        [Checkbox(description: "Opens a dialog box to rename the blueprint on saving and confirm overwrite (disables automatic numbering)")]
        public bool RenameBlueprint
        {
            get => renameBlueprint;
            set => SetField(ref renameBlueprint, value);
        }

        [Separator("Features")]
        [Checkbox(description: "Change the drag position on pasting grids, so you can point directly where the origin block should go")]
        public bool FixPastePosition
        {
            get => fixPastePosition;
            set => SetField(ref fixPastePosition, value);
        }

        [Checkbox(description: "Handle subgrids together with mechanical connection blocks (the ones which would be disconnected)")]
        public bool HandleSubgrids
        {
            get => handleSubgrids;
            set => SetField(ref handleSubgrids, value);
        }

        [Checkbox(description: "Holding Alt disables the placement test while pasting, use this only with great care")]
        public bool DisablePlacementTest
        {
            get => disablePlacementTest;
            set => SetField(ref disablePlacementTest, value);
        }

        [Checkbox(description: "Backup and restore associated blocks (toolbar slots, event and turret controllers)")]
        public bool RestoreToolbars
        {
            get => restoreToolbars;
            set => SetField(ref restoreToolbars, value);
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

        [Slider(0f, 0.9f, 0.01f, description: "Vertical position of the box size and hints on the screen")]
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

        [Slider(0f, 10f, 1f, SliderAttribute.SliderType.Integer, description: "Text shadow offset (set to zero to turn off text shadows)")]
        public int TextShadowOffset
        {
            get => textShadowOffset;
            set => SetField(ref textShadowOffset, value);
        }

        [Color(hasAlpha: true, description: "Box size text color")]
        public Color TextShadowColor
        {
            get => textShadowColor;
            set => SetField(ref textShadowColor, value);
        }

        [Separator("Block Selection")]
        [Slider(1f, 10f, 1f, SliderAttribute.SliderType.Integer, description: "Density of the highlights (number of overdraws)")]
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

        #endregion

        #region Property change notification bilerplate

        public static readonly Config Default = new Config();
        public static readonly Config Current = ConfigStorage.Load();

        public event PropertyChangedEventHandler PropertyChanged;

        protected virtual void OnPropertyChanged(string propertyName)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
        }

        private bool SetField<T>(ref T field, T value, [CallerMemberName] string propertyName = null)
        {
            if (EqualityComparer<T>.Default.Equals(field, value)) return false;
            field = value;
            OnPropertyChanged(propertyName);
            return true;
        }

        #endregion
    }
}