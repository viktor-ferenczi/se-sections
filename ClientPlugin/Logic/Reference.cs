using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using HarmonyLib;
using Sandbox.Common.ObjectBuilders;
using Sandbox.Game.Entities;
using Sandbox.Game.Entities.Blocks;
using Sandbox.Game.Entities.Cube;
using Sandbox.Game.EntityComponents;
using Sandbox.Game.Screens.Helpers;
using Sandbox.ModAPI;
using SpaceEngineers.Game.Entities.Blocks;
using SpaceEngineers.Game.EntityComponents.Blocks;
using SpaceEngineers.Game.ModAPI.Ingame;
using VRage.ObjectBuilder;
using Group = System.Collections.Generic.Dictionary<string, string>;
using IngameIMyFunctionalBlock =  Sandbox.ModAPI.Ingame.IMyFunctionalBlock;

namespace ClientPlugin.Logic
{
    public abstract class Reference : DataStorage
    {
        public static Reference CreateForTerminalBlock(MyTerminalBlock terminalBlock)
        {
            switch (terminalBlock)
            {
                case MyRemoteControl b:
                    return new RemoteControl(b);

                case MyEventControllerBlock b:
                    return new EventController(b);

                case MyTurretControlBlock b:
                    return new TurretController(b);
                
                case MyOffensiveCombatBlock b:
                    return new OffensiveCombat(b);
                
                case MyPathRecorderBlock b:
                    // AI Recorder block
                    return new PathRecorder(b);

                case MyButtonPanel b:
                    return new ButtonPanel(b);
                
                case MyDefensiveCombatBlock _:
                case MySensorBlock _:
                case MyFlightMovementBlock _:
                case MyShipController _:
                case MyTimerBlock _:
                    return new ToolbarOwner(terminalBlock);
            }
            return new Referred(terminalBlock);
        }

        protected Reference(MyTerminalBlock terminalBlock) : base(terminalBlock)
        {
        }
        
        // Backups the block associations from the built block into storage data,
        // but only the valid items (skips any grayed out toolbar slots or invalid block list items)
        public abstract void Backup(Dictionary<long, Reference> referenceByBlock);

        // Restores the block associations from storage data into the built block,
        // but only if the current association in the block is invalid
        // (grayed out toolbar slot or invalid block list item)
        public abstract void Restore(Dictionary<long, Reference> referenceByBlock, Dictionary<string, Reference> referenceByGuid);

        protected static bool TryBackupBlockId(Dictionary<long, Reference> referenceByBlock, Group group, string key, long blockId)
        {
            if (blockId == 0 || !referenceByBlock.TryGetValue(blockId, out var reference))
                return false;

            group[key] = reference.Guid;
            return true;
        }
        
        protected bool TryRestoreBlockId(Dictionary<long, Reference> referenceByBlock, Dictionary<string, Reference> referenceByGuid, Dictionary<string, string> group, string key, long blockId, out long restoredBlockId)
        {
            restoredBlockId = 0;

            if (blockId != 0 && referenceByBlock.ContainsKey(blockId))
                return false;
                
            if (!group.TryGetValue(key, out var guid))
                return false;
                
            if (!referenceByGuid.TryGetValue(guid, out var reference))
                return false;

            restoredBlockId = reference.TerminalBlock.EntityId;
            return true;
        }
    }

    public class Referred : Reference
    {
        public Referred(MyTerminalBlock terminalBlock) : base(terminalBlock)
        {
        }

        public override void Backup(Dictionary<long, Reference> referenceByBlock)
        {
        }

        public override void Restore(Dictionary<long, Reference> referenceByBlock, Dictionary<string, Reference> referenceByGuid)
        {
        }
    }
    
    public class ToolbarOwner : Reference
    {
        private const string GroupName = "Toolbar";
        private readonly MyToolbar toolbar;

        public ToolbarOwner(MyTerminalBlock terminalBlock) : base(terminalBlock)
        {
            toolbar = terminalBlock.GetToolbar();
        }

        public override void Backup(Dictionary<long, Reference> referenceByBlock)
        {
            var itemCount = toolbar.SlotCount * toolbar.PageCount;
            var group = GetOrCreateGroup(GroupName, itemCount);
            BackupToolbar(referenceByBlock, group, toolbar);
        }

        public override void Restore(Dictionary<long, Reference> referenceByBlock, Dictionary<string, Reference> referenceByGuid)
        {
            if (!Groups.TryGetValue(GroupName, out var group))
                return;

            RestoreToolbar(referenceByBlock, referenceByGuid, group, toolbar);
            
            // Toolbar items do not need change notifications to be sent, because ItemChanged
            // has already been invoked by SetItemAtIndex whenever required
        }

        public static void BackupToolbar(Dictionary<long, Reference> referenceByBlock, Group group, MyToolbar toolbar)
        {
            var itemCount = toolbar.SlotCount * toolbar.PageCount;
            for (var i = 0; i < itemCount; i++)
            {
                if (!(toolbar.GetItemAtIndex(i) is MyToolbarItemTerminalBlock terminalBlockItem))
                    continue;

                TryBackupBlockId(referenceByBlock, group, i.ToString(), terminalBlockItem.BlockEntityId);
            }
        }
        
        public static void RestoreToolbar(Dictionary<long, Reference> referenceByBlock, Dictionary<string, Reference> referenceByGuid, Group group, MyToolbar toolbar)
        {
            foreach (var kv in group)
            {
                if (!int.TryParse(kv.Key, out var i))
                    continue;
                
                if (i < 0 || i >= toolbar.ItemCount)
                    continue;
                
                if (!(toolbar.GetItemAtIndex(i) is MyToolbarItemTerminalBlock terminalBlockItem))
                    continue;
                
                if (referenceByBlock.ContainsKey(terminalBlockItem.BlockEntityId))
                    continue;

                if (!referenceByGuid.TryGetValue(kv.Value, out var reference))
                    continue;

                var itemBuilder = (MyObjectBuilder_ToolbarItemTerminalBlock)terminalBlockItem.GetObjectBuilder();
                itemBuilder.BlockEntityId = reference.TerminalBlock.EntityId;
                toolbar.SetItemAtIndex(i, MyToolbarItemFactory.CreateToolbarItem(itemBuilder));
            }
        }
    }

    public class RemoteControl : ToolbarOwner
    {
        private const string GroupName = "RemoteControl";
        private MyRemoteControl Block => (MyRemoteControl)TerminalBlock; 

        public RemoteControl(MyTerminalBlock terminalBlock) : base(terminalBlock)
        {
        }
        
        public override void Backup(Dictionary<long, Reference> referenceByBlock)
        {
            base.Backup(referenceByBlock);
            
            var group = GetOrCreateGroup(GroupName);
            TryBackupBlockId(referenceByBlock, group, "Camera", Block.GetBoundCameraSync().Value);
        }

        public override void Restore(Dictionary<long, Reference> referenceByBlock, Dictionary<string, Reference> referenceByGuid)
        {
            base.Restore(referenceByBlock, referenceByGuid);

            if (!Groups.TryGetValue(GroupName, out var group)) 
                return;

            if (TryRestoreBlockId(referenceByBlock, referenceByGuid, group, "Camera", Block.GetBoundCameraSync().Value, out var cameraBlockId))
            {
                Block.GetBoundCameraSync().Value = cameraBlockId;
            }
        }
    }

    public class EventController : ToolbarOwner
    {
        private const string GroupName = "EventController";
        private MyEventControllerBlock Block => (MyEventControllerBlock)TerminalBlock; 

        public EventController(MyTerminalBlock terminalBlock) : base(terminalBlock)
        {
        }
        
        public override void Backup(Dictionary<long, Reference> referenceByBlock)
        {
            base.Backup(referenceByBlock);
            
            var group = GetOrCreateGroup(GroupName);
            var selectedBlocks = Block.GetSelectedBlocks();
            var i = 0;
            foreach (var blockId in selectedBlocks.Keys)
            {
                TryBackupBlockId(referenceByBlock, group, (i++).ToString(), blockId);
            }
        }

        public override void Restore(Dictionary<long, Reference> referenceByBlock, Dictionary<string, Reference> referenceByGuid)
        {
            base.Restore(referenceByBlock, referenceByGuid);
            
            if (!Groups.TryGetValue(GroupName, out var group))
                return;

            if (group.Count == 0)
                return;

            var selectedBlockIds = Block.GetSelectedBlockIds();
            var blockIdsToRemove = selectedBlockIds?.Where(blockId => !referenceByBlock.ContainsKey(blockId)).ToList();
            
            var blockIdsToAdd = new List<long>(group.Count);
            foreach (var guid in group.Values)
            { 
                if(!referenceByGuid.TryGetValue(guid, out var reference))
                    continue;
                    
                if (selectedBlockIds != null && selectedBlockIds.Contains(reference.TerminalBlock.EntityId))
                    continue;

                blockIdsToAdd.Add(reference.TerminalBlock.EntityId);
            }

            if (blockIdsToRemove != null && blockIdsToRemove.Count != 0)
                Block.RemoveBlocks(blockIdsToRemove);
            
            if (blockIdsToAdd.Count != 0)
                Block.AddBlocks(blockIdsToAdd);
        }
    }

    public class TurretController : Reference
    {
        private const string TurretControlGroupName = "Turret";
        private const string ToolsGroupName = "Tools";
        private IMyTurretControlBlock Block => (IMyTurretControlBlock)TerminalBlock; 

        public TurretController(MyTerminalBlock terminalBlock) : base(terminalBlock)
        {
        }
        
        public override void Backup(Dictionary<long, Reference> referenceByBlock)
        {
            var group = GetOrCreateGroup(TurretControlGroupName);
            TryBackupBlockId(referenceByBlock, group, "AzimuthRotor", Block.AzimuthRotor?.EntityId ?? 0);
            TryBackupBlockId(referenceByBlock, group, "ElevationRotor", Block.ElevationRotor?.EntityId ?? 0);
            TryBackupBlockId(referenceByBlock, group, "Camera", Block.Camera?.EntityId ?? 0);
            
            group = GetOrCreateGroup(ToolsGroupName);
            var tools = new List<IngameIMyFunctionalBlock>();
            Block.GetTools(tools);
            var i = 0;
            foreach (var tool in tools)
            {
                TryBackupBlockId(referenceByBlock, group, (i++).ToString(), tool.EntityId);
            }
        }

        public override void Restore(Dictionary<long, Reference> referenceByBlock, Dictionary<string, Reference> referenceByGuid)
        {
            if (Groups.TryGetValue(TurretControlGroupName, out var group))
            {
                if(TryRestoreBlockId(referenceByBlock, referenceByGuid, group, "AzimuthRotor", Block.AzimuthRotor?.EntityId ?? 0, out var azimuthBlockId))
                    Block.AzimuthRotor = (MyMotorStator)referenceByBlock[azimuthBlockId].TerminalBlock;

                if(TryRestoreBlockId(referenceByBlock, referenceByGuid, group, "ElevationRotor", Block.ElevationRotor?.EntityId ?? 0, out var elevationBlockId))
                    Block.ElevationRotor = (MyMotorStator)referenceByBlock[elevationBlockId].TerminalBlock;

                if(TryRestoreBlockId(referenceByBlock, referenceByGuid, group, "Camera", Block.Camera?.EntityId ?? 0, out var cameraBlockId))
                    Block.Camera = (MyCameraBlock)referenceByBlock[cameraBlockId].TerminalBlock;
            }

            if (Groups.TryGetValue(ToolsGroupName, out group) && group.Count != 0)
            {
                var tools = new List<IngameIMyFunctionalBlock>();
                Block.GetTools(tools);
                var blockIdsToAdd = new List<IngameIMyFunctionalBlock>(group.Count);
                var blockIdsToRemove = new List<IngameIMyFunctionalBlock>(group.Count);
                foreach (var guid in group.Values)
                { 
                    if(!referenceByGuid.TryGetValue(guid, out var reference))
                        continue;
                    
                    if (tools.Contains((IngameIMyFunctionalBlock)reference.TerminalBlock))
                    {
                        blockIdsToRemove.Add((IngameIMyFunctionalBlock)reference.TerminalBlock);
                        continue;
                    }

                    blockIdsToAdd.Add((IngameIMyFunctionalBlock)reference.TerminalBlock);
                }

                if (blockIdsToAdd.Count == 0) 
                    return;

                Block.RemoveTools(blockIdsToRemove.Take(blockIdsToAdd.Count).ToList());
                Block.AddTools(blockIdsToAdd);
            }
        }
    }
    
    public class OffensiveCombat : Reference
    {
        private const string WeaponsGroupName = "Weapons";
        private MyOffensiveCombatBlock Block => (MyOffensiveCombatBlock)TerminalBlock;

        public OffensiveCombat(MyTerminalBlock terminalBlock) : base(terminalBlock)
        {
        }
        
        public override void Backup(Dictionary<long, Reference> referenceByBlock)
        {
            if (!Block.Components.TryGet<MyOffensiveCombatCircleOrbit>(out var component))
                return;

            var group = GetOrCreateGroup(WeaponsGroupName);
            var selectedWeapons = new List<long>();
            component.GetSelectedWeapons(selectedWeapons);
            var i = 0;
            foreach (var blockId in selectedWeapons)
            {
                TryBackupBlockId(referenceByBlock, group, (i++).ToString(), blockId);
            }
        }

        public override void Restore(Dictionary<long, Reference> referenceByBlock, Dictionary<string, Reference> referenceByGuid)
        {
            if (!Groups.TryGetValue(WeaponsGroupName, out var group))
                return;
            
            if (!Block.Components.TryGet<MyOffensiveCombatCircleOrbit>(out var component))
                return;

            var selectedWeapons = new List<long>();
            component.GetSelectedWeapons(selectedWeapons);

            var modified = false;
            foreach (var guid in group.Values)
            {
                if (!referenceByGuid.TryGetValue(guid, out var reference))
                    continue;
                
                if (selectedWeapons.Contains(reference.TerminalBlock.EntityId))
                    continue;
                
                selectedWeapons.Add(reference.TerminalBlock.EntityId);
                modified = true;
            }

            if (modified)
            {
                component.SetSelectedWeapons(selectedWeapons);
            }
        }
    }
    
    public class PathRecorder : Reference
    {
        private const string WaypointGroupName = "Waypoint:{0}";
        private MyPathRecorderBlock Block => (MyPathRecorderBlock)TerminalBlock;

        public PathRecorder(MyTerminalBlock terminalBlock) : base(terminalBlock)
        {
        }
        
        public override void Backup(Dictionary<long, Reference> referenceByBlock)
        {
            if (!Block.GetComponent(out MyPathRecorderComponent component))
                return;

            var i = 0;
            foreach (var waypoint in component.Waypoints)
            {
                var group = GetOrCreateGroup(string.Format(WaypointGroupName, i++));
                ToolbarOwner.BackupToolbar(referenceByBlock, group, waypoint.Toolbar);
            }
        }

        public override void Restore(Dictionary<long, Reference> referenceByBlock, Dictionary<string, Reference> referenceByGuid)
        {
            if (!Block.GetComponent(out MyPathRecorderComponent component))
                return;

            var i = 0;
            foreach (var waypoint in component.Waypoints)
            {
                if (!Groups.TryGetValue(string.Format(WaypointGroupName, i++), out var group))
                    continue;
                
                ToolbarOwner.RestoreToolbar(referenceByBlock, referenceByGuid, group, waypoint.Toolbar);
            }
        }
    }
    
    public class ButtonPanel : ToolbarOwner
    {
        private const string GroupName = "ButtonPanel";
        private MyButtonPanel Block => (MyButtonPanel)TerminalBlock; 

        public ButtonPanel(MyTerminalBlock terminalBlock) : base(terminalBlock)
        {
        }
        
        public override void Backup(Dictionary<long, Reference> referenceByBlock)
        {
            base.Backup(referenceByBlock);
            
            var group = GetOrCreateGroup(GroupName);
            var builder = (MyObjectBuilder_ButtonPanel)Block.GetObjectBuilderCubeBlock();
            foreach (var pos in builder.CustomButtonNames.Dictionary.Keys)
            {
                var customName = builder.CustomButtonNames[pos];
                if (customName != null)
                {
                    group[$"Name{pos}"] = customName;
                }
            }
        }

        public override void Restore(Dictionary<long, Reference> referenceByBlock, Dictionary<string, Reference> referenceByGuid)
        {
            base.Restore(referenceByBlock, referenceByGuid);
            
            if (!Groups.TryGetValue(GroupName, out var group))
                return;

            if (group.Count == 0)
                return;

            foreach (var (key, value) in group)
            {
                if (key.StartsWith("Name"))
                {
                    if (int.TryParse(key.Substring(4), out var pos))
                    {
                        Block.SetCustomButtonName(value, pos);
                    }
                }
            }
        }
    }
}