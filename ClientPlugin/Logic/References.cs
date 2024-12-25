using System;
using System.Collections.Generic;
using System.Linq;
using Sandbox.Game.Entities;
using Sandbox.Game.Entities.Cube;
using Sandbox.Game.Gui;

namespace ClientPlugin.Logic
{
    public class References
    {
        // Block references by block EntityId, this is always unique and all terminal blocks present
        private readonly Dictionary<long, Reference> referencesByBlock = new Dictionary<long, Reference>();
        
        // Block references by GUID, uniqueness is ensured by assigning a new GUID to copied blocks
        private readonly Dictionary<string, Reference> referencesByGuid = new Dictionary<string, Reference>();

        public References(MyCubeGrid grid)
        {
            // FIXME: Use the mechanical (physical) group to find all subgrids, that should be faster
            var mechanicalConnections = new MechanicalConnections(grid);
            var grids = mechanicalConnections.IterGrids.ToList();
            InitFromGrids(grids);
        }

        public References(List<MyCubeGrid> grids)
        {
            InitFromGrids(grids);
        }

        private void InitFromGrids(List<MyCubeGrid> grids)
        {
            foreach (var grid in grids)
            {
                foreach (var slimBlock in grid.CubeBlocks)
                {
                    if (!(slimBlock.FatBlock is MyTerminalBlock terminalBlock))
                        continue;

                    var reference = Reference.CreateForTerminalBlock(terminalBlock);
                    referencesByBlock[terminalBlock.EntityId] = reference;
                    
                    // Copied blocks with the same GUID get a new one assigned,
                    // so they are not assigned to the wrong slot by mistake
                    if (referencesByGuid.ContainsKey(reference.Guid))
                    {
                        reference.GenerateNewGuid();
                        reference.WriteStorage();
                    }

                    referencesByGuid[reference.Guid] = reference;
                }
            }
        }

        public void Backup()
        {
            foreach (var reference in referencesByBlock.Values)
            {
                reference.Backup(referencesByBlock);
                reference.WriteStorage();
            }
        }

        public void Restore()
        {
            foreach (var reference in referencesByBlock.Values)
            {
                reference.Restore(referencesByBlock, referencesByGuid);
            }
        }

        public static void ClearBlockReferenceData(MyCubeGrid mainGrid)
        {
            if (mainGrid == null)
                return;
            
            // FIXME: Use the mechanical (physical) group to find all subgrids, that should be faster
            var mechanicalConnections = new MechanicalConnections(mainGrid);
            var grids = mechanicalConnections.IterGrids.ToList();
            foreach (var grid in grids)
                ClearBlockReferenceDataFromSubgrid(grid);
        }

        private static void ClearBlockReferenceDataFromSubgrid(MyCubeGrid grid)
        {
            foreach (var slimBlock in grid.CubeBlocks)
            {
                if (!(slimBlock.FatBlock is MyTerminalBlock terminalBlock))
                    continue;
                
                terminalBlock.RemoveStorage();
            }
        }
    }
}