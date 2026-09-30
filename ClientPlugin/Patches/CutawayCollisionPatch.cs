using System.Collections.Generic;
using System.Reflection;
using ClientPlugin.Logic;
using HarmonyLib;
using Havok;
using Sandbox.Game.Entities;
using Sandbox.Game.Entities.Cube;
using VRageMath;

namespace ClientPlugin.Patches
{
    [HarmonyPatch]
    public static class CutawayCollisionPatch
    {
        private static readonly System.Type Collector = typeof(MyCubeGrid).Assembly.GetType(
            "Sandbox.Game.Entities.Cube.MyCubeBlockCollector",
            true
        );
        private static readonly MethodInfo AddMass = AccessTools.DeclaredMethod(
            Collector,
            "AddMass"
        );

        private static MethodBase TargetMethod() =>
            AccessTools.DeclaredMethod(Collector, "CollectBlock");

        private static bool Prefix(
            object __instance,
            MySlimBlock block,
            IDictionary<Vector3I, HkMassElement> massResults
        )
        {
            if (!Cutaway.IsHidden(block))
                return true;

            // Skip shape generation before armor segmentation, but retain the real ship's mass.
            if (massResults != null && block.BlockDefinition.HasPhysics && block.CubeGrid != null)
                AddMass.Invoke(__instance, new object[] { block, massResults });
            return false;
        }
    }
}
