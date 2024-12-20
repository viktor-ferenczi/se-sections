using System;
using System.Collections.Generic;
using System.Linq;
using Sandbox.Game.Entities;
using Sandbox.Game.Entities.Blocks;
using Sandbox.Game.Entities.Cube;

namespace ClientPlugin.Logic
{
    public class MechanicalConnections
    {
        private readonly HashSet<MyCubeGrid> grids = new HashSet<MyCubeGrid>();
        private readonly HashSet<MechanicalConnection> mechanicalConnections = new HashSet<MechanicalConnection>();

        public MechanicalConnections(MyCubeGrid mainGrid)
        {
            WalkSubgrids(mainGrid);
        }

        private void WalkSubgrids(MyCubeGrid grid)
        {
            if (grid == null || grid.Closed || !grid.InScene || grid.Physics == null || grids.Contains(grid))
                return;

            grids.Add(grid);

            foreach (var slimBlock in grid.CubeBlocks)
            {
                switch (slimBlock.FatBlock)
                {
                    case MyMechanicalConnectionBlockBase baseBlock:
                    {
                        var topBlock = baseBlock.TopBlock;
                        var topGrid = topBlock?.CubeGrid;
                        if (topGrid == null)
                            break;
                        mechanicalConnections.Add(new MechanicalConnection(baseBlock, topBlock));
                        WalkSubgrids(topGrid);
                        break;
                    }

                    case MyAttachableTopBlockBase topBlock:
                    {
                        var baseBlock = topBlock.Stator;
                        var baseGrid = baseBlock?.CubeGrid;
                        if (baseGrid == null)
                            break;
                        mechanicalConnections.Add(new MechanicalConnection(baseBlock, topBlock));
                        WalkSubgrids(baseGrid);
                        break;
                    }
                }
            }
        }

        public void RemoveConnections(IEnumerable<MySlimBlock> blocks)
        {
            foreach (var slimBlock in blocks)
            {
                switch (slimBlock.FatBlock)
                {
                    case MyMechanicalConnectionBlockBase baseBlock:
                    {
                        var topBlock = baseBlock.TopBlock;
                        var topGrid = topBlock?.CubeGrid;
                        if (topGrid == null)
                            break;
                        mechanicalConnections.Remove(new MechanicalConnection(baseBlock, topBlock));
                        break;
                    }

                    case MyAttachableTopBlockBase topBlock:
                    {
                        var baseBlock = topBlock.Stator;
                        var baseGrid = baseBlock?.CubeGrid;
                        if (baseGrid == null)
                            break;
                        mechanicalConnections.Remove(new MechanicalConnection(baseBlock, topBlock));
                        break;
                    }
                }
            }
        }

        public HashSet<MyCubeGrid> FindUnreachableSubgrids(MyCubeGrid grid)
        {
            var unreachable = new HashSet<MyCubeGrid>(grids);
            var stack = new List<MyCubeGrid> { grid };
            while (stack.Count != 0)
            {
                var subgrid = stack.Pop();
                if (!unreachable.Contains(subgrid))
                    continue;

                unreachable.Remove(subgrid);

                // NOTE: This algorithm is suboptimal due to its O(N*M) time complexity,
                // where N is the number of subgrids and M is the number of mechanical connections.
                // It should be performant enough up to 100 subgrids and 1000 mechanical connections, which is realistic.
                // Above that we would need acceleration disctionaries to find the mechanical connections per grid.
                // That would improve the time complexity to O(N*log2(M)) plus the acceleration structure overhead.
                stack.AddRange(mechanicalConnections.Where(mc => mc.BaseGrid == subgrid).Select(mc => mc.TopGrid));
                stack.AddRange(mechanicalConnections.Where(mc => mc.TopGrid == subgrid).Select(mc => mc.BaseGrid));
            }

            return unreachable;
        }
    }
}