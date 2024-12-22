using System;
using System.Collections.Generic;
using System.Reflection;
using Sandbox.Definitions;
using Sandbox.Game.Entities.Cube;
using Sandbox.Game.EntityComponents;
using VRage.Game;
using VRage.Game.Definitions;
using VRage.Game.ObjectBuilders.ComponentSystem;
using VRage.ObjectBuilders;

namespace ClientPlugin.Logic
{
    public static class ModStorage
    {
        private static readonly Guid ModStorageGuid = new Guid("cd844fa4-4ac0-4d9c-8a01-73416b225772");
        private static bool modStorageComponentDefinitionRegistered;

        public static void RegisterModStorageComponentDefinition()
        {
            if (modStorageComponentDefinitionRegistered)
                return;

            modStorageComponentDefinitionRegistered = true;

            // CustomData is defined in Content\Data\EntityComponents.sbc
            // We need to define our own entity component here, otherwise the game removes the data.
            // Credits: Thanks goes to Pas2704 for providing the code in this method.
            var def = new MyModStorageComponentDefinition();
            var id = new SerializableDefinitionId(typeof(MyObjectBuilder_ModStorageComponent), "BlockAssociations");
            def.Init(new MyObjectBuilder_ModStorageComponentDefinition
            {
                SubtypeName = "BlockAssociations",
                Id = id,
                RegisteredStorageGuids = new[] { ModStorageGuid }
            }, MyModContext.UnknownContext);

            var entityContainersField = typeof(MyDefinitionManager)
                .GetNestedType("DefinitionSet", BindingFlags.NonPublic)
                .GetField("m_entityComponentDefinitions", BindingFlags.Instance | BindingFlags.NonPublic);

            var dict = (Dictionary<MyDefinitionId, MyComponentDefinitionBase>)entityContainersField.GetValue(MyDefinitionManager.Static.Definitions);
            dict[id] = def;
        }

        private static bool TryGetStorage(this MyTerminalBlock terminalBlock, out string value)
        {
            var storage = terminalBlock.Storage;
            if (storage == null)
            {
                value = null;
                return false;
            }

            return storage.TryGetValue(ModStorageGuid, out value);
        }

        private static void SetStorage(this MyTerminalBlock terminalBlock, string value)
        {
            var storage = terminalBlock.Storage;
            if (storage == null)
            {
                terminalBlock.Storage = storage = new MyModStorageComponent();
                terminalBlock.Components.Add(storage);
            }

            if (!storage.TryGetValue(ModStorageGuid, out var oldValue) || value != oldValue)
            {
                storage[ModStorageGuid] = value;
            }
        }
    }
}