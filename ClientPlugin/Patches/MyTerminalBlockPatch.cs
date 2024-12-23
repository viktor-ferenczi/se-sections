using System.Diagnostics.CodeAnalysis;
using ClientPlugin.Logic;
using HarmonyLib;
using Sandbox.Game.Entities.Cube;
using Sandbox.Game.Gui;
using Sandbox.Game.Localization;
using Sandbox.Graphics.GUI;
using VRage.Game.ModAPI;
using VRage.Utils;

namespace ClientPlugin.Patches
{
    [HarmonyPatch(typeof(MyTerminalBlock))]
    [SuppressMessage("ReSharper", "UnusedMember.Local")]
    // ReSharper disable once UnusedType.Global
    public static class MyTerminalBlockPatch
    {
        private static MyGuiScreenTextPanel textPanel;
        private static bool controlAdded;

        [HarmonyPostfix]
        [HarmonyPatch("CreateTerminalControls")]
        private static void CreateTerminalControlsPostfix()
        {
            if (controlAdded)
                return;
            
            MyTerminalControlFactory.AddControl(new MyTerminalControlButton<MyTerminalBlock>("BlockReferenceData", MyStringId.GetOrCompute("Block Reference Data"), MySpaceTexts.Terminal_CustomDataTooltip, BlockReferenceDataClicked)
            {
                Enabled = (MyTerminalBlock x) => true,
                SupportsMultipleBlocks = false
            });

            controlAdded = true;
        }

        private static void BlockReferenceDataClicked(MyTerminalBlock terminalBlock)
        {
            var description = terminalBlock.TryGetStorage(out var v) ? v : "";
            textPanel = new MyGuiScreenTextPanel("Block Reference Data", "", "Data stored by the Sections plugin to allow\nfor restoring block references on pasting grids.", description, result => OnClosedTextBox(result, terminalBlock), null, null, true);
            MyGuiScreenGamePlay.TmpGameplayScreenHolder = MyGuiScreenGamePlay.ActiveGameplayScreen;
            MyScreenManager.AddScreen(MyGuiScreenGamePlay.ActiveGameplayScreen = textPanel);
        }

        private static void OnClosedTextBox(ResultEnum result, MyTerminalBlock terminalBlock)
        {
            if (result == ResultEnum.OK)
                terminalBlock.SetStorage(textPanel.Description.Text.ToString());

            textPanel = null;
        }
    }
}