using System.Diagnostics.CodeAnalysis;
using HarmonyLib;
using Sandbox.Game.Entities;

namespace ClientPlugin.Patches
{
    [HarmonyPatch(typeof(MyCubeGrid))]
    [SuppressMessage("ReSharper", "UnusedMember.Local")]
    // ReSharper disable once UnusedType.Global
    public static class MyCubeGridPatch
    {
        [HarmonyPostfix]
        [HarmonyPatch(nameof(MyCubeGrid.PasteBlocksToGrid))]
        private static void PasteBlocksToGridPostfix(MyCubeGrid __instance)
        {
            Logic.Logic.Static.PasteBlocksToGridPostfix(__instance);
        }
    }
}