using System.Collections.Generic;
using System.Linq;
using Sandbox.Game.Entities;
using VRage.Game;
using VRageMath;

namespace Shared.Logic
{
    // Section editing on the authoritative grid: offline, on a host, or on a
    // dedicated server for a client. Input, dialogs and the clipboard stay in the client.
    public sealed class SectionEditor
    {
        private readonly MyCubeGrid grid;
        private readonly BoundingBoxI box;
        private readonly bool includeIntersectingBlocks;
        private readonly bool handleSubgrids;

        public HashSet<Vector3I> BlockMinPositions { get; private set; }
        public HashSet<MyCubeGrid> Subgrids { get; private set; }

        public SectionEditor(
            MyCubeGrid grid,
            BoundingBoxI box,
            bool includeIntersectingBlocks,
            bool handleSubgrids
        )
        {
            this.grid = grid;
            this.box = box;
            this.includeIntersectingBlocks = includeIntersectingBlocks;
            this.handleSubgrids = handleSubgrids;
        }

        public void BackupReferences() => new References(grid).Backup();

        // The blocks inside the box on the grid, then the subgrids which would be orphaned
        // by removing them. Both are known after this, before anything is built or removed.
        public void Collect()
        {
            // Collect all mechanical connections inside the mechanical group
            var mechanicalConnections = new MechanicalConnections(grid);

            // Collect the Min coordinates of blocks considered to be inside the selection
            var blockMinSet = CollectMinOfBlocksInBox();
            BlockMinPositions = blockMinSet;

            // Delete mechanical connections where the base or the top block is in the selection
            mechanicalConnections.RemoveConnections(
                grid.CubeBlocks.Where(b => blockMinSet.Contains(b.Min))
            );

            // Any grid which becomes unreachable from the main grid must be copied together with the selected blocks
            Subgrids = handleSubgrids
                ? mechanicalConnections.FindUnreachableSubgrids(grid)
                : new HashSet<MyCubeGrid>();
        }

        // The origin block is the first cube block of the first grid, pasting puts it under
        // the crosshair. The displayed size goes into the name of the copy.
        public List<MyObjectBuilder_CubeGrid> CreateGridBuilders(
            Vector3I? originBlockMin,
            string sizeText
        )
        {
            if (BlockMinPositions == null)
                Collect();
            var blockMinSet = BlockMinPositions;

            // Create the grid builders
            var mainGridBuilder = CreateMainGridBuilder(blockMinSet, originBlockMin, sizeText);
            var gridBuilders = new List<MyObjectBuilder_CubeGrid>(1 + Subgrids.Count)
            {
                mainGridBuilder,
            };
            gridBuilders.AddRange(
                Subgrids.Select(subgrid => (MyObjectBuilder_CubeGrid)subgrid.GetObjectBuilder())
            );

            // Remap EntityIds to avoid duplicates on pasting.
            // It will disconnect all block toolbar slot and EC/TC block list entry connections between
            // the copied blocks (and subgrids) with the remaining blocks (and subgrids).
            // This is why we need a mechanism to store these connections,
            // so these connections can be restored on pasting those blocks (and subgrids) back.
            MyEntities.RemapObjectBuilderCollection(gridBuilders);

            // Sanity check
            if (mainGridBuilder.CubeBlocks.Count == 0)
                return gridBuilders;

            MoveOriginFirst(mainGridBuilder, OriginBlockMin(blockMinSet, originBlockMin));
            return gridBuilders;
        }

        public void Delete()
        {
            if (BlockMinPositions == null)
                Collect();

            foreach (var min in BlockMinPositions)
            {
                grid.RemoveBlock(grid.GetCubeBlock(min), true);
            }

            grid.RecalcBounds();
            grid.RecalculateOwners();
            grid.Physics.AddDirtyArea(box.Min, box.Max);

            foreach (var subgrid in Subgrids)
            {
                subgrid.Close();
            }
        }

        private HashSet<Vector3I> CollectMinOfBlocksInBox()
        {
            return grid
                .CubeBlocks.Where(block =>
                    includeIntersectingBlocks
                        ? box.Intersects(new BoundingBoxI(block.Min, block.Max))
                        : box.Contains(block.Min) == ContainmentType.Contains
                            && box.Contains(block.Max) == ContainmentType.Contains
                )
                .Select(block => block.Min)
                .ToHashSet();
        }

        private MyObjectBuilder_CubeGrid CreateMainGridBuilder(
            HashSet<Vector3I> blockMinSet,
            Vector3I? originBlockMin,
            string sizeText
        )
        {
            // Keep only the blocks in selection by their Min coordinates
            var gridBuilder = (MyObjectBuilder_CubeGrid)grid.GetObjectBuilder();
            gridBuilder.CubeBlocks = gridBuilder
                .CubeBlocks.Where(b => blockMinSet.Contains(b.Min))
                .ToList();

            // Set the name, it will be the basis for saving the grid as a blueprint
            gridBuilder.DisplayName = $"{gridBuilder.DisplayName} {sizeText}";

            // Sanity check
            if (gridBuilder.CubeBlocks.Count == 0)
                return gridBuilder;

            // Strip down block groups to contain only the blocks preserved
            foreach (var group in gridBuilder.BlockGroups)
            {
                group.Blocks = group.Blocks.Where(min => blockMinSet.Contains(min)).ToList();
            }

            // Remove empty block groups
            gridBuilder.BlockGroups = gridBuilder
                .BlockGroups.Where(group => group.Blocks.Count != 0)
                .ToList();

            MoveOriginFirst(gridBuilder, OriginBlockMin(blockMinSet, originBlockMin));
            return gridBuilder;
        }

        // The aimed block if it is selected, otherwise a corner of the selection
        private static Vector3I OriginBlockMin(
            HashSet<Vector3I> blockMinSet,
            Vector3I? originBlockMin
        ) =>
            originBlockMin.HasValue && blockMinSet.Contains(originBlockMin.Value)
                ? originBlockMin.Value
                : blockMinSet.FindCorner();

        private static void MoveOriginFirst(
            MyObjectBuilder_CubeGrid gridBuilder,
            Vector3I originMin
        )
        {
            var originBlockIndex = gridBuilder.CubeBlocks.FindIndex(b =>
                (Vector3I)b.Min == originMin
            );
            if (originBlockIndex <= 0)
                return;

            // Move the block to the head of the cube list, that marks it as the origin one
            var originBlockBuilder = gridBuilder.CubeBlocks[originBlockIndex];
            gridBuilder.CubeBlocks.RemoveAt(originBlockIndex);
            gridBuilder.CubeBlocks.Insert(0, originBlockBuilder);
        }
    }
}
