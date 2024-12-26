using System.Collections.Generic;
using System.Diagnostics;
using System.Diagnostics.CodeAnalysis;
using System.Reflection;
using HarmonyLib;
using Sandbox.Game.Entities;

namespace ClientPlugin.Patches
{
    [HarmonyPatch]
    [SuppressMessage("ReSharper", "UnusedMember.Global")]
    // ReSharper disable once UnusedType.Global
    public static class PasteGridDataPatch
    {
        public static MethodBase TargetMethod()
        {
            var clsMyCubeGrid = typeof(MyCubeGrid);
            var clsPasteGridData = clsMyCubeGrid.GetNestedType("PasteGridData", BindingFlags.NonPublic);
            var method = AccessTools.DeclaredMethod(clsPasteGridData, "TryPasteGrid");
            Debug.Assert(method != null);
            return method;
        }

        public static void Postfix(List<MyCubeGrid> ___m_pastedGrids)
        {
            Logic.Logic.Static.TryPasteGridPostfix(___m_pastedGrids);
        }
    }
}