using System.Collections.Generic;
using System.Reflection;
using HarmonyLib;
using VRage.Input;
using VRage.Utils;

namespace ClientPlugin.Patches
{
    [HarmonyPatch]
    public static class SelectionInputPatch
    {
        // HUD components poll controls independently of the gameplay screen.
        private static IEnumerable<MethodBase> TargetMethods()
        {
            yield return AccessTools.DeclaredMethod(
                typeof(MyVRageInput),
                nameof(MyVRageInput.IsNewGameControlPressed)
            );
            yield return AccessTools.DeclaredMethod(
                typeof(MyVRageInput),
                nameof(MyVRageInput.IsGameControlPressed)
            );
        }

        [HarmonyPrefix]
        private static bool Prefix(MyStringId controlId, ref bool __result)
        {
            if (!Logic.Logic.Static.ShouldSuppressGameControl(controlId))
                return true;
            __result = false;
            return false;
        }
    }
}
