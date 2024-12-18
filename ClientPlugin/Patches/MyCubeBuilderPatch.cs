using System.Diagnostics.CodeAnalysis;
using HarmonyLib;
using Sandbox.Game.Entities;

namespace ClientPlugin.Patches
{
    [HarmonyPatch(typeof(MyCubeBuilder))]
    [SuppressMessage("ReSharper", "InconsistentNaming")]
    [SuppressMessage("ReSharper", "UnusedMember.Local")]
    // ReSharper disable once UnusedType.Global
    public class MyCubeBuilderPatch
    {
        [HarmonyPrefix]
        [HarmonyPatch(nameof(MyCubeBuilder.HandleGameInput))]
        private static bool HandleGameInputPrefix(ref bool __result)
        {
            if (Logic.Logic.Static.HandleGameInput())
            {
                // Input has been handled
                __result = true;
                return false;
            }

            return true;
        }

        [HarmonyPrefix]
        [HarmonyPatch(nameof(MyCubeBuilder.Draw))]
        private static bool DrawPrefix(MyCubeBuilder __instance)
        {
            return Logic.Logic.Static.DrawPrefix(__instance);
        }
    }
}