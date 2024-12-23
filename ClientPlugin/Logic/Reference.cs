using System.Collections.Generic;
using Sandbox.Common.ObjectBuilders;
using Sandbox.Game.Entities;
using Sandbox.Game.Entities.Blocks;
using Sandbox.Game.Entities.Cube;
using Sandbox.Game.Screens.Helpers;
using SpaceEngineers.Game.Entities.Blocks;

namespace ClientPlugin.Logic
{
    public abstract class Reference : DataStorage
    {
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
        private const string DataSection = "ToolbarSlots";
        private readonly MyToolbar toolbar;

        public ToolbarOwner(MyTerminalBlock terminalBlock) : base(terminalBlock)
        {
            toolbar = terminalBlock.GetToolbar();
        }

        public override void Backup(Dictionary<long, Reference> referenceByBlock)
        {
            if (!Groups.TryGetValue(DataSection, out var guids))
            {
                var toolbarItemCount = toolbar.ItemCount;
                guids = Groups[DataSection] = new Dictionary<string, string>(8);
            }

            var itemCount = toolbar.SlotCount * toolbar.PageCount;
            for (var i = 0; i < itemCount; i++)
            {
                if (!(toolbar.GetItemAtIndex(i) is MyToolbarItemTerminalBlock terminalBlockItem))
                    continue;
                
                if (!referenceByBlock.TryGetValue(terminalBlockItem.BlockEntityId, out var reference))
                    continue;

                guids[i.ToString()] = reference.Guid;
            }
        }

        public override void Restore(Dictionary<long, Reference> referenceByBlock, Dictionary<string, Reference> referenceByGuid)
        {
            if (!Groups.TryGetValue(DataSection, out var guids))
                return;

            foreach (var kv in guids)
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

    public class EventController : ToolbarOwner
    {
        public List<string> SelectedBlockGuids;

        public EventController(MyTerminalBlock terminalBlock) : base(terminalBlock)
        {
        }
    }

    public class TurretController : ToolbarOwner
    {
        public string AzimuthGuid;
        public string ElevationGuid;
        public string CameraGuid;

        public TurretController(MyTerminalBlock terminalBlock) : base(terminalBlock)
        {
        }
    }

    public class RemoteControl : ToolbarOwner
    {
        public string CameraGuid;

        public RemoteControl(MyTerminalBlock terminalBlock) : base(terminalBlock)
        {
        }
    }
}