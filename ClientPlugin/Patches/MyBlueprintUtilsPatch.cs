using System.Diagnostics.CodeAnalysis;
using HarmonyLib;
using Sandbox.Game.GUI;

namespace ClientPlugin.Patches
{
    [HarmonyPatch(typeof(MyBlueprintUtils))]
    [SuppressMessage("ReSharper", "InconsistentNaming")]
    [SuppressMessage("ReSharper", "UnusedMember.Local")]
    // ReSharper disable once UnusedType.Global
    public class MyBlueprintUtilsPatch
    {
        [HarmonyPostfix]
        [HarmonyPatch(nameof(MyBlueprintUtils.SaveToDisk))]
        private static void SaveToDiskPostfix(ref string filePath)
        {
            Logic.Logic.Static.SaveToDiskPostfix(filePath);
        }
    }
}