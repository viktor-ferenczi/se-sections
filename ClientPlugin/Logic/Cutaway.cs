using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using Sandbox.Game.Entities;
using Sandbox.Game.Entities.Cube;
using Sandbox.Game.GUI;
using Sandbox.Game.World;
using Sandbox.ModAPI;
using VRage.Audio;
using VRage.Game.Entity;
using VRageMath;

namespace ClientPlugin.Logic
{
    public static class Cutaway
    {
        // The physics collector also runs on worker threads.
        private static readonly ConcurrentDictionary<MySlimBlock, HiddenBlock> Hidden =
            new ConcurrentDictionary<MySlimBlock, HiddenBlock>();

        public static bool IsHidden(MySlimBlock block) => Hidden.ContainsKey(block);

        public static Vector3 HiddenColor(MySlimBlock block)
        {
            var color = block.ColorMaskHSV;
            color.Y = (color.Y + 1f) * (Config.Current.HiddenBlockSaturation / 100f) - 1f;
            return color;
        }

        public static void RefreshVisual(MySlimBlock block)
        {
            if (block != null && Hidden.TryGetValue(block, out var state))
                state.HideEntity(block.FatBlock, block.Dithering, HiddenColor(block));
        }

        private static readonly Dictionary<MyCubeGrid, HashSet<Vector3I>> Masks =
            new Dictionary<MyCubeGrid, HashSet<Vector3I>>();
        private static readonly ConcurrentQueue<MySlimBlock> AddedBlocks =
            new ConcurrentQueue<MySlimBlock>();

        private static readonly HashSet<MySlimBlock> Automatic = new HashSet<MySlimBlock>();
        private static readonly HashSet<MySlimBlock> AutoCandidates = new HashSet<MySlimBlock>();
        private static readonly HashSet<MySlimBlock> AutoGridBlocks = new HashSet<MySlimBlock>();
        public static bool AutoHideEnabled => Config.Current.AutoHideBlocks;

        public static bool SetAutoHide(bool enabled, bool force = false)
        {
            if (
                !enabled
                && !force
                && AutoHideEnabled
                && IsAllowed
                && CharacterIntersectsHiddenBlock()
            )
            {
                MyGuiAudio.PlaySound(MyGuiSounds.HudUnable);
                MyAPIGateway.Utilities.ShowMessage(
                    "Sections",
                    "Cannot turn off auto-hide while your character overlaps a hidden block. Move clear first."
                );
                return true;
            }
            var allowed = enabled && IsAllowed && MySession.Static.LocalCharacter != null;
            if (allowed)
                return true;
            foreach (var block in Automatic)
                if (!IsManuallyHidden(block))
                    RestoreBlock(block);
            Automatic.Clear();
            return false;
        }

        private static bool CharacterIntersectsHiddenBlock()
        {
            var character = MySession.Static.LocalCharacter;
            if (character == null || character.IsDead)
                return false;
            var characterBounds = new MyOrientedBoundingBoxD(
                character.PositionComp.LocalAABB,
                character.WorldMatrix
            );
            foreach (var block in Automatic)
            {
                var grid = block.CubeGrid;
                if (
                    grid == null
                    || grid.Closed
                    || grid.MarkedForClose
                    || !block.BlockDefinition.HasPhysics
                )
                    continue;
                var halfCube = new Vector3D(grid.GridSize * 0.5);
                var bounds = new MyOrientedBoundingBoxD(
                    new BoundingBoxD(
                        (Vector3D)block.Min * grid.GridSize - halfCube,
                        (Vector3D)block.Max * grid.GridSize + halfCube
                    ),
                    grid.WorldMatrix
                );
                if (characterBounds.Intersects(ref bounds))
                    return true;
            }
            return false;
        }

        private static bool IsManuallyHidden(MySlimBlock block) =>
            block.CubeGrid != null
            && Masks.TryGetValue(block.CubeGrid, out var mask)
            && Cells(block).Any(mask.Contains);

        private static void UpdateAutomatic()
        {
            AutoCandidates.Clear();
            var character = MySession.Static.LocalCharacter;
            if (AutoHideEnabled && character != null && !character.IsDead)
            {
                var sphere = new BoundingSphereD(
                    character.PositionComp.GetPosition(),
                    Config.Current.AutoHideRadius
                );
                var nearby = MyEntities.GetTopMostEntitiesInSphere(ref sphere);
                var grids = nearby.OfType<MyCubeGrid>().ToArray();
                nearby.Clear();
                foreach (var owner in grids)
                {
                    if (
                        !CanApply(owner)
                        || owner.Closed
                        || owner.MarkedForClose
                        || owner.Physics == null
                        || owner.IsPreview
                    )
                        continue;
                    owner.GetBlocksInsideSphere(ref sphere, AutoGridBlocks);
                    AutoCandidates.UnionWith(AutoGridBlocks);
                }
            }
            foreach (var block in Automatic)
                if (!AutoCandidates.Contains(block) && !IsManuallyHidden(block))
                    RestoreBlock(block);
            foreach (var block in AutoCandidates)
                if (!Hidden.ContainsKey(block))
                    HideBlock(block);
            Automatic.Clear();
            Automatic.UnionWith(AutoCandidates);
        }

        private static void OnBlockAdded(MySlimBlock block) => AddedBlocks.Enqueue(block);

        public static int ApplyBox(MyCubeGrid grid, BoundingBoxI box, bool hide, bool intersecting)
        {
            if (!CanApply(grid) || grid.Physics == null || grid.IsPreview)
                return 0;
            if (!Masks.TryGetValue(grid, out var mask))
            {
                if (!hide)
                    return 0;
                Masks.Add(grid, mask = new HashSet<Vector3I>());
                grid.OnBlockAdded += OnBlockAdded;
            }
            var count = 0;
            foreach (var block in grid.CubeBlocks)
            {
                var bounds = new BoundingBoxI(block.Min, block.Max);
                if (
                    !(
                        intersecting
                            ? box.Intersects(bounds)
                            : box.Contains(bounds) == ContainmentType.Contains
                    )
                )
                    continue;
                foreach (var cell in Cells(block))
                {
                    if (hide)
                        mask.Add(cell);
                    else
                        mask.Remove(cell);
                }
                if (hide ? HideBlock(block) : !Automatic.Contains(block) && RestoreBlock(block))
                    count++;
            }
            if (mask.Count == 0)
            {
                grid.OnBlockAdded -= OnBlockAdded;
                Masks.Remove(grid);
            }
            return count;
        }

        private static IEnumerable<Vector3I> Cells(MySlimBlock block)
        {
            for (var x = block.Min.X; x <= block.Max.X; x++)
            for (var y = block.Min.Y; y <= block.Max.Y; y++)
            for (var z = block.Min.Z; z <= block.Max.Z; z++)
                yield return new Vector3I(x, y, z);
        }

        private static bool HideBlock(MySlimBlock block)
        {
            var state = new HiddenBlock(block.Dithering, block.CubeGrid);
            state.CaptureEntity(block.FatBlock);
            if (!Hidden.TryAdd(block, state))
                return false;
            block.Dithering = Config.Current.HiddenBlockOpacity / 100f - 1f;
            block.UpdateVisual(false);
            RefreshVisual(block);
            block.CubeGrid.Physics?.AddDirtyArea(block.Min, block.Max);
            return true;
        }

        public static bool IsAllowed =>
            MySession.Static != null
            && MySession.Static.Ready
            && !MySession.Static.IsUnloading
            && (
                !Sandbox.Game.Multiplayer.Sync.MultiplayerActive
                || MySession.Static.CreativeMode
                || MySession.Static.IsUserAdmin(Sandbox.Game.Multiplayer.Sync.MyId)
            )
            && (
                MySession.Static.CreativeMode
                || MySession.Static.IsUserAdmin(Sandbox.Game.Multiplayer.Sync.MyId)
                || MySession.Static.CreativeToolsEnabled(Sandbox.Game.Multiplayer.Sync.MyId)
            );

        public static bool CanApply(MyCubeGrid grid) =>
            IsAllowed
            && grid != null
            && (
                MySession.Static.IsUserAdmin(Sandbox.Game.Multiplayer.Sync.MyId)
                || grid.BigOwners.Contains(MySession.Static.LocalPlayerId)
            );

        public static int Restore(
            MyCubeGrid grid = null,
            bool stopAutomatic = true,
            bool force = false
        )
        {
            if (stopAutomatic)
            {
                if (force)
                    Config.Current.StopAutoHide();
                else
                    Config.Current.AutoHideBlocks = false;
                if (AutoHideEnabled)
                    return 0;
            }
            if (grid == null)
                while (AddedBlocks.TryDequeue(out _)) { }
            foreach (
                var owner in Masks.Keys.Where(owner => grid == null || owner == grid).ToArray()
            )
            {
                owner.OnBlockAdded -= OnBlockAdded;
                Masks.Remove(owner);
            }
            var count = 0;
            foreach (
                var block in Hidden
                    .Keys.Where(block => grid == null || block.CubeGrid == grid)
                    .ToArray()
            )
                if (RestoreBlock(block))
                    count++;
            return count;
        }

        private static bool RestoreBlock(MySlimBlock block)
        {
            if (!Hidden.TryRemove(block, out var state))
                return false;
            state.Restore();
            var owner = block.CubeGrid;
            if (
                owner == null
                || owner.Closed
                || owner.MarkedForClose
                || owner.GetCubeBlock(block.Position) != block
            )
                return false;
            block.Dithering = state.Dithering;
            block.UpdateVisual(false);
            owner.Physics?.AddDirtyArea(block.Min, block.Max);
            return true;
        }

        public static void Update()
        {
            if (!IsAllowed)
            {
                Restore(force: true);
                return;
            }

            foreach (
                var owner in Masks
                    .Keys.Where(owner => owner.Closed || owner.MarkedForClose || !CanApply(owner))
                    .ToArray()
            )
                Restore(owner, stopAutomatic: false);
            while (AddedBlocks.TryDequeue(out var added))
            {
                if (added.CubeGrid == null)
                    continue;
                if (!Masks.TryGetValue(added.CubeGrid, out var mask))
                {
                    RestoreBlock(added);
                    continue;
                }
                // Placement and paste always uncover every cube occupied by the new block.
                foreach (var cell in Cells(added))
                    mask.Remove(cell);
                RestoreBlock(added);
                if (mask.Count == 0)
                {
                    added.CubeGrid.OnBlockAdded -= OnBlockAdded;
                    Masks.Remove(added.CubeGrid);
                }
            }

            UpdateAutomatic();
            foreach (var entry in Hidden)
            {
                var block = entry.Key;
                var grid = block.CubeGrid;
                if (
                    grid == null
                    || grid.Closed
                    || grid.MarkedForClose
                    || grid.GetCubeBlock(block.Position) != block
                )
                {
                    if (Hidden.TryRemove(block, out var state))
                        state.Restore();
                    continue;
                }
                if (grid != entry.Value.Grid || !CanApply(grid))
                {
                    RestoreBlock(block);
                    continue;
                }
                // Doors and other animated blocks can recreate or re-enable their subparts.
                var dithering = Config.Current.HiddenBlockOpacity / 100f - 1f;
                if (
                    block.Dithering != dithering
                    || entry.Value.Saturation != Config.Current.HiddenBlockSaturation
                )
                {
                    block.Dithering = dithering;
                    entry.Value.Saturation = Config.Current.HiddenBlockSaturation;
                    block.UpdateVisual(false);
                }
                RefreshVisual(block);
            }
        }

        private sealed class HiddenBlock
        {
            public readonly float Dithering;
            public readonly MyCubeGrid Grid;
            public float Saturation = Config.Current.HiddenBlockSaturation;
            private readonly Dictionary<MyEntity, bool> visibility =
                new Dictionary<MyEntity, bool>();
            private readonly Dictionary<Sandbox.Engine.Physics.MyPhysicsBody, bool> physics =
                new Dictionary<Sandbox.Engine.Physics.MyPhysicsBody, bool>();
            private readonly Dictionary<MyEntity, float> transparency =
                new Dictionary<MyEntity, float>();
            private readonly Dictionary<MyEntity, Vector3> colors =
                new Dictionary<MyEntity, Vector3>();

            public HiddenBlock(float dithering, MyCubeGrid grid)
            {
                Dithering = dithering;
                Grid = grid;
            }

            public void CaptureEntity(MyEntity entity)
            {
                if (
                    entity == null
                    || entity.Closed
                    || entity.MarkedForClose
                    || visibility.ContainsKey(entity)
                )
                    return;
                visibility.Add(entity, entity.Render.Visible);
                transparency.Add(entity, entity.Render.Transparency);
                colors.Add(entity, entity.Render.ColorMaskHsv);
                if (
                    entity.Physics is Sandbox.Engine.Physics.MyPhysicsBody body
                    && !physics.ContainsKey(body)
                )
                    physics.Add(body, body.Enabled);
                if (entity.Subparts != null)
                    foreach (var part in entity.Subparts.Values)
                        CaptureEntity(part);
            }

            public void HideEntity(MyEntity entity, float dithering, Vector3 color)
            {
                if (entity == null || entity.Closed || entity.MarkedForClose)
                    return;
                CaptureEntity(entity);
                var visible = visibility[entity] && dithering > -1f;
                if (entity.Render.Visible != visible)
                    entity.Render.Visible = visible;
                if (entity.Render.ColorMaskHsv != color)
                    entity.Render.ColorMaskHsv = color;
                if (entity.Render.Transparency != dithering)
                {
                    entity.Render.Transparency = dithering;
                    entity.Render.UpdateTransparency();
                }
                if (entity.Physics is Sandbox.Engine.Physics.MyPhysicsBody body)
                {
                    if (!physics.ContainsKey(body))
                        physics.Add(body, body.Enabled);
                    if (body.Enabled)
                        body.Enabled = false;
                }
                if (entity.Subparts != null)
                    foreach (var part in entity.Subparts.Values)
                        HideEntity(part, dithering, color);
            }

            public void Restore()
            {
                foreach (var entry in visibility)
                    if (!entry.Key.Closed && !entry.Key.MarkedForClose)
                    {
                        entry.Key.Render.Visible = entry.Value;
                        entry.Key.Render.ColorMaskHsv = colors[entry.Key];
                        entry.Key.Render.Transparency = transparency[entry.Key];
                        entry.Key.Render.UpdateTransparency();
                    }
                foreach (var entry in physics)
                    if (
                        entry.Key.Entity != null
                        && !entry.Key.Entity.Closed
                        && !entry.Key.Entity.MarkedForClose
                    )
                        entry.Key.Enabled = entry.Value;
            }
        }
    }
}
