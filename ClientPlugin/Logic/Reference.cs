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
                
                case MySensorBlock _:
                case MyButtonPanel _:
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
            for (var i = 0; i < itemCount; i++)
            {
                if (!(toolbar.GetItemAtIndex(i) is MyToolbarItemTerminalBlock terminalBlockItem))
                    continue;

                TryBackupBlockId(referenceByBlock, group, i.ToString(), terminalBlockItem.BlockEntityId);
            }
        }

        public override void Restore(Dictionary<long, Reference> referenceByBlock, Dictionary<string, Reference> referenceByGuid)
        {
            if (!Groups.TryGetValue(GroupName, out var group))
                return;

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
            
            // Toolbar items do not need change notifications to be sent, because ItemChanged
            // has already been invoked by SetItemAtIndex whenever required
        }
    }

    public class RemoteControl : ToolbarOwner
    {
        private const string GroupName = "RemoteControl";
        private MyRemoteControl RemoteControlBlock => (MyRemoteControl)TerminalBlock; 

        public RemoteControl(MyTerminalBlock terminalBlock) : base(terminalBlock)
        {
        }
        
        public override void Backup(Dictionary<long, Reference> referenceByBlock)
        {
            base.Backup(referenceByBlock);
            
            var group = GetOrCreateGroup(GroupName);
            TryBackupBlockId(referenceByBlock, group, "Camera", RemoteControlBlock.GetBoundCameraSync().Value);
        }

        public override void Restore(Dictionary<long, Reference> referenceByBlock, Dictionary<string, Reference> referenceByGuid)
        {
            base.Restore(referenceByBlock, referenceByGuid);

            if (!Groups.TryGetValue(GroupName, out var group)) 
                return;

            if (TryRestoreBlockId(referenceByBlock, referenceByGuid, group, "Camera", RemoteControlBlock.GetBoundCameraSync().Value, out var cameraBlockId))
            {
                RemoteControlBlock.GetBoundCameraSync().Value = cameraBlockId;
                RemoteControlBlock.RaisePropertiesChanged();
            }
        }
    }

    public class EventController : ToolbarOwner
    {
        private const string GroupName = "EventController";
        private MyEventControllerBlock EventControllerBlock => (MyEventControllerBlock)TerminalBlock; 

        public EventController(MyTerminalBlock terminalBlock) : base(terminalBlock)
        {
        }
        
        public override void Backup(Dictionary<long, Reference> referenceByBlock)
        {
            base.Backup(referenceByBlock);
            
            var group = GetOrCreateGroup(GroupName);
            var selectedBlocks = EventControllerBlock.GetSelectedBlocks();
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

            var selectedBlockIds = EventControllerBlock.GetSelectedBlockIds();
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
                EventControllerBlock.RemoveBlocks(blockIdsToRemove);
            
            if (blockIdsToAdd.Count != 0)
                EventControllerBlock.AddBlocks(blockIdsToAdd);
        }
    }

    public class TurretController : Reference
    {
        private const string TurretControlGroupName = "TurretControl";
        private const string ToolsGroupName = "Tools";
        private IMyTurretControlBlock TurretControlBlock => (IMyTurretControlBlock)TerminalBlock; 

        public TurretController(MyTerminalBlock terminalBlock) : base(terminalBlock)
        {
        }
        
        public override void Backup(Dictionary<long, Reference> referenceByBlock)
        {
            var group = GetOrCreateGroup(TurretControlGroupName);
            TryBackupBlockId(referenceByBlock, group, "AzimuthRotor", TurretControlBlock.AzimuthRotor?.EntityId ?? 0);
            TryBackupBlockId(referenceByBlock, group, "ElevationRotor", TurretControlBlock.ElevationRotor?.EntityId ?? 0);
            TryBackupBlockId(referenceByBlock, group, "Camera", TurretControlBlock.Camera?.EntityId ?? 0);
            
            group = GetOrCreateGroup(ToolsGroupName);
            var tools = new List<IngameIMyFunctionalBlock>();
            TurretControlBlock.GetTools(tools);
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
                if(TryRestoreBlockId(referenceByBlock, referenceByGuid, group, "AzimuthRotor", TurretControlBlock.AzimuthRotor?.EntityId ?? 0, out var azimuthBlockId))
                    TurretControlBlock.AzimuthRotor = (MyMotorStator)referenceByBlock[azimuthBlockId].TerminalBlock;

                if(TryRestoreBlockId(referenceByBlock, referenceByGuid, group, "ElevationRotor", TurretControlBlock.ElevationRotor?.EntityId ?? 0, out var elevationBlockId))
                    TurretControlBlock.ElevationRotor = (MyMotorStator)referenceByBlock[elevationBlockId].TerminalBlock;

                if(TryRestoreBlockId(referenceByBlock, referenceByGuid, group, "Camera", TurretControlBlock.Camera?.EntityId ?? 0, out var cameraBlockId))
                    TurretControlBlock.Camera = (MyCameraBlock)referenceByBlock[cameraBlockId].TerminalBlock;
            }

            if (Groups.TryGetValue(ToolsGroupName, out group) && group.Count != 0)
            {
                var tools = new List<IngameIMyFunctionalBlock>();
                TurretControlBlock.GetTools(tools);
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

                TurretControlBlock.RemoveTools(blockIdsToRemove.Take(blockIdsToAdd.Count).ToList());
                TurretControlBlock.AddTools(blockIdsToAdd);
            }
        }
    }
}