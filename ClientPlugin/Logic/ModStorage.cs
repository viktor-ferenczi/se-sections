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
        public const string ModStorageComponentSubtypeName = "BlockReferenceData";
        private static readonly Guid ModStorageGuid = new Guid("cd844fa4-4ac0-4d9c-8a01-73416b225772");

        public static void RegisterModStorageComponentDefinition()
        {
            // CustomData is defined in Content\Data\EntityComponents.sbc
            // We need to define our own entity component here, otherwise the game removes the data.
            // Credits: Thanks goes to Pas2704 for providing the code in this method.
            var def = new MyModStorageComponentDefinition();
            var id = new SerializableDefinitionId(typeof(MyObjectBuilder_ModStorageComponent), ModStorageComponentSubtypeName);
            def.Init(new MyObjectBuilder_ModStorageComponentDefinition
            {
                SubtypeName = ModStorageComponentSubtypeName,
                Id = id,
                RegisteredStorageGuids = new[] { ModStorageGuid }
            }, MyModContext.UnknownContext);

            var entityContainersField = typeof(MyDefinitionManager)
                .GetNestedType("DefinitionSet", BindingFlags.NonPublic)
                .GetField("m_entityComponentDefinitions", BindingFlags.Instance | BindingFlags.NonPublic);

            var dict = (Dictionary<MyDefinitionId, MyComponentDefinitionBase>)entityContainersField.GetValue(MyDefinitionManager.Static.Definitions);
            dict[id] = def;
        }

        public static bool TryGetStorage(this MyTerminalBlock terminalBlock, out string value)
        {
            var storage = terminalBlock.Storage;
            if (storage == null)
            {
                value = null;
                return false;
            }

            return storage.TryGetValue(ModStorageGuid, out value);
        }

        public static void SetStorage(this MyTerminalBlock terminalBlock, string value)
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

        public static void RemoveStorage(this MyTerminalBlock terminalBlock)
        {
            terminalBlock.Storage?.Remove(ModStorageGuid);
        }
    }
}