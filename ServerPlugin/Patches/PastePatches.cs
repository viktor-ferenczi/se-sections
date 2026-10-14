using System.Collections.Generic;
using System.Reflection;
using HarmonyLib;
using Sandbox.Game.Entities;
using VRage.Network;

namespace ServerPlugin.Patches;

// Pasted grids get their block references back, as offline. The paste requests of the
// clients run here, on the server.
[HarmonyPatch]
public static class PasteGridPatch
{
    private static MethodBase TargetMethod() =>
        AccessTools.DeclaredMethod(
            typeof(MyCubeGrid).GetNestedType("PasteGridData", BindingFlags.NonPublic),
            "TryPasteGrid"
        );

    private static void Postfix(List<MyCubeGrid> ___m_pastedGrids, EndpointId ___SenderEndpointId)
    {
        if (___m_pastedGrids != null)
            Companion.OnPasted(___m_pastedGrids, ___SenderEndpointId.Value);
    }
}

// Pasting onto a grid: a client's request lands in this event handler
[HarmonyPatch(typeof(MyCubeGrid), "PasteBlocksToGridServer_Implementation")]
public static class PasteBlocksToGridPatch
{
    private static void Postfix(MyCubeGrid __instance)
    {
        var context = MyEventContext.Current;
        var paster = context.IsValid && !context.IsLocallyInvoked ? context.Sender.Value : 0UL;
        Companion.OnPasted(new[] { __instance }, paster);
    }
}
