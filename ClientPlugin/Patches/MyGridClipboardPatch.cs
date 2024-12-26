using System.Diagnostics.CodeAnalysis;
using System.Linq;
using HarmonyLib;
using Sandbox.Game.Entities.Cube;
using VRage.Game;
using VRageMath;

namespace ClientPlugin.Patches
{
    [HarmonyPatch(typeof(MyGridClipboard))]
    [SuppressMessage("ReSharper", "UnusedMember.Local")]
    // ReSharper disable once UnusedType.Global
    public static class MyGridClipboardPatch
    {
        [HarmonyPrefix]
        [HarmonyPatch(nameof(MyGridClipboard.SetGridFromBuilder))]
        private static bool SetGridFromBuilderPrefix(MyObjectBuilder_CubeGrid grid, ref Vector3 dragPointDelta)
        {
            if (!Config.Current.FixPastePosition)
                return true;

            // Pick out the "origin" block which was faced while making the blueprint.
            // It is always the first cube block of the main subgrid (first grid).
            var firstBlock = grid?.CubeBlocks.FirstOrDefault();
            if (firstBlock != null)
                FixDragPointOnPaste(grid, firstBlock, ref dragPointDelta);

            return true;
        }

        [HarmonyPrefix]
        [HarmonyPatch(nameof(MyGridClipboard.SetGridFromBuilders))]
        private static bool SetGridFromBuildersPrefix(MyObjectBuilder_CubeGrid[] grids, ref Vector3 dragPointDelta)
        {
            if (!Config.Current.FixPastePosition)
                return true;

            // Pick out the "origin" block which was faced while making the blueprint.
            // It is always the first cube block of the main subgrid (first grid).
            var firstGrid = grids.FirstOrDefault();
            var firstBlock = firstGrid?.CubeBlocks.FirstOrDefault();
            if (firstBlock != null)
                FixDragPointOnPaste(firstGrid, firstBlock, ref dragPointDelta);

            return true;
        }

        private static void FixDragPointOnPaste(MyObjectBuilder_CubeGrid grid, MyObjectBuilder_CubeBlock firstBlock, ref Vector3 dragPointDelta)
        {
            // Override the drag point to the center of the origin block, considering the position and
            // orientation of the main subgrid, but not the block orientation. It will point to a corner
            // cube if the origin block is larger than 1x1x1, but that should not be an issue.
            // var po = grid.PositionAndOrientation ?? MyPositionAndOrientation.Default;
            var gridSize = grid.GridSizeEnum == MyCubeSize.Large ? 2.5f : 0.5f;
            var minPos = new Vector3(firstBlock.Min) * gridSize;
            // var offset = Vector3.Transform(-minPos, po.Orientation);
            dragPointDelta = -minPos;
        }
    }
}