using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Reflection;
using ClientPlugin.Logic;
using HarmonyLib;
using Sandbox.Engine.Physics;
using Sandbox.Game.Entities;
using Sandbox.Game.Entities.Cube;
using VRageMath;

namespace ClientPlugin.Patches
{
    // Blocks hidden without collision must not be picked as the build or remove target.
    [HarmonyPatch]
    public static class CutawayTargetingPatch
    {
        private static readonly MethodInfo TryGetValue = AccessTools.Method(
            typeof(ConcurrentDictionary<Vector3I, MyCube>),
            nameof(ConcurrentDictionary<Vector3I, MyCube>.TryGetValue)
        );
        private static readonly MethodInfo CubeExists = AccessTools.Method(
            typeof(MyCubeGrid),
            nameof(MyCubeGrid.CubeExists)
        );

        private static IEnumerable<MethodBase> TargetMethods()
        {
            // The aim ray: armor and model-intersected blocks are hit by their triangles.
            yield return AccessTools.Method(
                typeof(MyCubeGrid),
                nameof(MyCubeGrid.GetLineIntersectionExactGrid),
                new[]
                {
                    typeof(LineD).MakeByRefType(),
                    typeof(Vector3I).MakeByRefType(),
                    typeof(double).MakeByRefType(),
                    typeof(MyPhysics.HitInfo?),
                }
            );
            // The walk from the hit cube back toward the eye to find the free cell.
            yield return AccessTools.Method(
                typeof(MyBlockBuilderBase),
                "GetCubeAddAndRemovePositions"
            );
        }

        private static IEnumerable<CodeInstruction> Transpiler(
            IEnumerable<CodeInstruction> instructions
        )
        {
            foreach (var instruction in instructions)
            {
                if (instruction.Calls(TryGetValue))
                    instruction.operand = AccessTools.Method(
                        typeof(CutawayTargetingPatch),
                        nameof(TryGetSolidCube)
                    );
                else if (instruction.Calls(CubeExists))
                    instruction.operand = AccessTools.Method(
                        typeof(CutawayTargetingPatch),
                        nameof(SolidCubeExists)
                    );
                else
                {
                    yield return instruction;
                    continue;
                }
                instruction.opcode = System.Reflection.Emit.OpCodes.Call;
                yield return instruction;
            }
        }

        private static bool TryGetSolidCube(
            ConcurrentDictionary<Vector3I, MyCube> cubes,
            Vector3I position,
            out MyCube cube
        )
        {
            if (cubes.TryGetValue(position, out cube) && !Cutaway.IsCollisionHidden(cube.CubeBlock))
                return true;
            cube = null;
            return false;
        }

        private static bool SolidCubeExists(MyCubeGrid grid, Vector3I position)
        {
            var block = grid.GetCubeBlock(position);
            return block != null && !Cutaway.IsCollisionHidden(block);
        }
    }
}
