using System;
using System.Collections.Generic;
using System.Linq;
using Sandbox.Game.Entities;
using Sandbox.ModAPI;
using VRage.Game.ModAPI;
using VRageMath;

namespace Shared.Logic
{
    // Records section removals in the Undo plugin's history when Undo is loaded, through
    // its API (mod message 487710606, see Undo's Docs/API.md). No reference to Undo:
    // without it nothing happens. Undo records where the world changes, so this runs
    // offline, on a lobby host and on a dedicated server, never on a client.
    public static class UndoBridge
    {
        private const long UndoApiMessageId = 487710606L;

        private static Func<
            IMyCubeGrid,
            List<Vector3I>,
            List<IMyCubeGrid>,
            string,
            ulong,
            bool
        > recordRemoval;

        // Asked again until Undo answers: on a dedicated server it starts with the
        // first update after the world loaded, maybe after this plugin
        private static bool Connect()
        {
            if (recordRemoval != null)
                return true;

            MyAPIGateway.Utilities?.SendModMessage(
                UndoApiMessageId,
                (Action<Dictionary<string, Delegate>>)(
                    api =>
                    {
                        if (api.TryGetValue("RecordRemoval", out var function))
                            recordRemoval =
                                function
                                as Func<
                                    IMyCubeGrid,
                                    List<Vector3I>,
                                    List<IMyCubeGrid>,
                                    string,
                                    ulong,
                                    bool
                                >;
                    }
                )
            );
            return recordRemoval != null;
        }

        // Right before the blocks go. The Steam id is the player's who asked, 0 for
        // the local player.
        public static void RecordRemoval(
            MyCubeGrid grid,
            IEnumerable<Vector3I> blockMins,
            IEnumerable<MyCubeGrid> subgrids,
            string label,
            ulong steamId
        )
        {
            try
            {
                if (!Connect())
                    return;
                // False where Undo does not record for the player, nothing to do then
                recordRemoval(
                    grid,
                    blockMins.ToList(),
                    subgrids.Cast<IMyCubeGrid>().ToList(),
                    label,
                    steamId
                );
            }
            catch (Exception e)
            {
                Log.Warning($"Recording a removal in Undo failed: {e.Message}");
            }
        }
    }
}
