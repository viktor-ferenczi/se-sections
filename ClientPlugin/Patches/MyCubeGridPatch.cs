using System.Diagnostics.CodeAnalysis;
using HarmonyLib;
using Sandbox.Game.Entities;
using Sandbox.Game.Entities.Cube;
using VRageMath;

namespace ClientPlugin.Patches
{
    [HarmonyPatch(typeof(MyCubeGrid))]
    [SuppressMessage("ReSharper", "UnusedMember.Local")]
    // ReSharper disable once UnusedType.Global
    public static class MyCubeGridPatch
    {
        [HarmonyPostfix]
        [HarmonyPatch("UpdatePartInstanceData")]
        private static void UpdatePartInstanceDataPostfix(
            MyCubeGrid __instance,
            MyCubePart part,
            Vector3I cubePos
        )
        {
            var block = __instance.GetCubeBlock(cubePos);
            if (block != null && Logic.Cutaway.IsHidden(block))
                part.InstanceData.SetColorMaskHSV(
                    new Vector4(Logic.Cutaway.HiddenColor(block), block.Dithering)
                );
        }

        [HarmonyPostfix]
        [HarmonyPatch(nameof(MyCubeGrid.PasteBlocksToGrid))]
        private static void PasteBlocksToGridPostfix(MyCubeGrid __instance)
        {
            Logic.Logic.Static.PasteBlocksToGridPostfix(__instance);
        }
    }

    [HarmonyPatch(typeof(MyCubeBlock), nameof(MyCubeBlock.UpdateVisual))]
    public static class CutawayVisualPatch
    {
        private static void Postfix(MyCubeBlock __instance) =>
            Logic.Cutaway.RefreshVisual(__instance.SlimBlock);
    }
}
