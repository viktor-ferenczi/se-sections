using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using Sandbox.Game.Entities;
using Sandbox.Game.Entities.Blocks;
using Sandbox.Game.Entities.Cube;
using Sandbox.Game.Screens.Helpers;
using Sandbox.ModAPI;
using SpaceEngineers.Game.Entities.Blocks;
using VRage;
using VRage.Game;
using VRage.ObjectBuilder;
using VRage.Sync;
using VRageMath;

namespace ClientPlugin.Logic
{
    public static class Extensions
    {
        public static int IndexOfFirstNonzeroAxis(this Vector3I v)
        {
            if (v[0] != 0)
                return 0;
            if (v[1] != 0)
                return 1;
            if (v[2] != 0)
                return 2;
            return -1;
        }

        public static Vector3I GetClosestIntDirection(this Base6Directions.Direction[] closestDirections, Base6Directions.Direction direction)
        {
            return Base6Directions.IntDirections[(int)closestDirections[(int)direction]];
        }

        public static Base6Directions.Direction[] FindClosestDirectionsTo(this MatrixD matrix, MatrixD other)
        {
            var bestForward = Base6Directions.Direction.Forward;
            var bestUp = Base6Directions.Direction.Up;
            var bestFit = double.NegativeInfinity;

            var otherForwardVector = other.Forward;
            var otherUpVector = other.Up;

            for (var forwardIndex = 0; forwardIndex < 6; forwardIndex++)
            {
                var forward = (Base6Directions.Direction)forwardIndex;
                var forwardFit = matrix.GetDirectionVector(forward).Dot(otherForwardVector);

                for (var upIndex = 0; upIndex < 6; upIndex++)
                {
                    var up = (Base6Directions.Direction)upIndex;

                    if (up == forward || up == Base6Directions.GetOppositeDirection(forward))
                        continue;

                    var upFit = matrix.GetDirectionVector(up).Dot(otherUpVector);
                    var fit = forwardFit + upFit;
                    if (fit > bestFit)
                    {
                        bestForward = forward;
                        bestUp = up;
                        bestFit = fit;
                    }
                }
            }

            var bestLeft = Base6Directions.GetLeft(bestUp, bestForward);
            return new Base6Directions.Direction[6]
            {
                bestForward,
                Base6Directions.GetOppositeDirection(bestForward),
                bestLeft,
                Base6Directions.GetOppositeDirection(bestLeft),
                bestUp,
                Base6Directions.GetOppositeDirection(bestUp),
            };
        }

        public static Vector3I FindCorner(this HashSet<Vector3I> set)
        {
            if (set.Count == 0)
                return Vector3I.Zero;

            var floor = new Vector3I(
                set.Min(v => v.X),
                set.Min(v => v.Y),
                set.Min(v => v.X)
            );

            // FIXME: Possibility of integer overflow should a grid be larger than 25800 along all 3 axis
            return set.Select(v => v - floor).MinBy(v => Vector3I.Dot(v, v)) + floor;
        }

        public static void CensorWorldPosition(this IReadOnlyCollection<MyObjectBuilder_CubeGrid> gridBuilders)
        {
            if (gridBuilders == null || gridBuilders.Count == 0)
                return;

            var maybeMainGridPO = gridBuilders.First().PositionAndOrientation;
            if (!maybeMainGridPO.HasValue)
                return;

            var mainGridPosition = (Vector3D)maybeMainGridPO.Value.Position;

            foreach (var gridBuilder in gridBuilders)
            {
                if (!gridBuilder.PositionAndOrientation.HasValue)
                    continue;

                var gridPO = gridBuilder.PositionAndOrientation.Value;
                gridBuilder.PositionAndOrientation = new MyPositionAndOrientation(gridPO.Position - mainGridPosition, gridPO.Forward, gridPO.Up);
            }
        }

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public static MyToolbar GetToolbar(this MyTerminalBlock block)
        {
            switch (block)
            {
                case MySensorBlock b:
                    return b.Toolbar;
                case MyButtonPanel b:
                    return b.Toolbar;
                case MyEventControllerBlock b:
                    return b.Toolbar;
                case MyFlightMovementBlock b:
                    return b.Toolbar;
                case MyShipController b:
                    return b.Toolbar;
                case MyTimerBlock b:
                    return b.Toolbar;
            }

            return null;
        }

        private static readonly FieldInfo SelectedBlocksField = AccessTools.DeclaredField(typeof(MyEventControllerBlock), "m_selectedBlocks");

        public static Dictionary<long, IMyTerminalBlock> GetSelectedBlocks(this MyEventControllerBlock eventControllerBlock)
        {
            return (Dictionary<long, IMyTerminalBlock>)SelectedBlocksField.GetValue(eventControllerBlock);
        }

        private static readonly FieldInfo SelectedBlockIdsField = AccessTools.DeclaredField(typeof(MyEventControllerBlock), "m_selectedBlockIds");

        public static MySerializableList<long> GetSelectedBlockIds(this MyEventControllerBlock eventControllerBlock)
        {
            return (MySerializableList<long>)SelectedBlockIdsField.GetValue(eventControllerBlock);
        }

        private static readonly FieldInfo BoundCameraSyncField = AccessTools.DeclaredField(typeof(MyRemoteControl), "m_bindedCamera" /* sic */);

        public static Sync<long, SyncDirection.BothWays> GetBoundCameraSync(this MyRemoteControl remoteControlBlock)
        {
            return (Sync<long, SyncDirection.BothWays>)BoundCameraSyncField.GetValue(remoteControlBlock);
        }

        private static readonly MethodInfo AddBlocksMethod = AccessTools.DeclaredMethod(typeof(MyEventControllerBlock), "AddBlocks");

        public static void AddBlocks(this MyEventControllerBlock eventControllerBlock, List<long> toSync)
        {
            AddBlocksMethod.Invoke(eventControllerBlock, new[] { toSync });
        }

        private static readonly MethodInfo RemoveBlocksMethod = AccessTools.DeclaredMethod(typeof(MyEventControllerBlock), "RemoveBlocks");

        public static void RemoveBlocks(this MyEventControllerBlock eventControllerBlock, List<long> toSync)
        {
            RemoveBlocksMethod.Invoke(eventControllerBlock, new[] { toSync });
        }

        private static readonly MethodInfo ToolSelectionRequestMethod = AccessTools.DeclaredMethod(typeof(MyTurretControlBlock), "ToolSelectionRequest");

        public static void ToolSelectionRequest(this MyTurretControlBlock turretControlBlock, List<long> toSync)
        {
            ToolSelectionRequestMethod.Invoke(turretControlBlock, new[] { toSync });
        }
    }
}