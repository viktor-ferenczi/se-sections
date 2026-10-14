using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Sandbox.Game.Entities;
using Sandbox.Game.Entities.Cube;
using Sandbox.Game.Multiplayer;
using Sandbox.Game.World;
using Sandbox.ModAPI;
using Shared;
using Shared.Companion;
using VRage.Game;
using VRageMath;

namespace ClientPlugin.Companion
{
    // The client half of the server companion. A client of a dedicated server says Hello;
    // a server running the companion answers with the player's grants, then edits run
    // there and hidden blocks lose collision there for this player only. Without an
    // answer the plugin works as before.
    public static class CompanionClient
    {
        private const double HelloTimeoutS = 15;
        private const int FlushIntervalTicks = 6;
        private const double RevokedSeconds = 10;

        private sealed class PendingEdit
        {
            public EditOperation Operation;
            public Action<List<MyObjectBuilder_CubeGrid>> OnGrids;
            public byte[][] Parts;
            public int Received;
        }

        private static bool started;
        private static bool timedOut;
        private static DateTime helloUtc;
        private static (bool RestoreToolbars, bool HandleSubgrids) sentOptions;
        private static int nextRequestId;
        private static int tick;

        private static readonly Dictionary<int, PendingEdit> pending =
            new Dictionary<int, PendingEdit>();
        private static readonly Dictionary<long, Dictionary<Vector3I, bool>> pendingHide =
            new Dictionary<long, Dictionary<Vector3I, bool>>();
        private static readonly Dictionary<long, DateTime> revokedUntil =
            new Dictionary<long, DateTime>();

        public static bool Served { get; private set; }
        public static Grants Grants { get; private set; }

        private static bool IsServerClient => Sync.MultiplayerActive && !Sync.IsServer;

        public static bool CanEdit => Served && IsServerClient && Grants.Edit;

        public static bool CanHideCollision => Served && IsServerClient && Grants.Cutaway;

        public static bool CanEditGrid(MyCubeGrid grid) =>
            CanEdit && grid != null && (Grants.AnyGrid || OwnsGrid(grid));

        // Where the server decides, the same rule as there
        public static bool CanHideCollisionOn(MyCubeGrid grid) =>
            CanHideCollision && !IsRevoked(grid) && (Grants.AnyGrid || OwnsGrid(grid));

        private static bool OwnsGrid(MyCubeGrid grid) =>
            grid.BigOwners.Contains(MySession.Static.LocalPlayerId);

        private static bool IsRevoked(MyCubeGrid grid) =>
            revokedUntil.TryGetValue(grid.EntityId, out var until) && DateTime.UtcNow < until;

        public static void Update()
        {
            if (!started)
            {
                if (
                    IsServerClient
                    && MySession.Static?.Ready == true
                    && MyAPIGateway.Multiplayer != null
                )
                    Start();
                return;
            }

            var options = (Config.Current.RestoreToolbars, Config.Current.HandleSubgrids);
            if (options != sentOptions && (DateTime.UtcNow - helloUtc).TotalSeconds >= 1)
                SendHello();

            if (!Served && !timedOut && (DateTime.UtcNow - helloUtc).TotalSeconds > HelloTimeoutS)
            {
                timedOut = true;
                Log.Info(
                    "The server does not run the Sections companion, editing stays off and cutaways are visual only"
                );
            }

            if (++tick % FlushIntervalTicks == 0)
                FlushHide();
        }

        private static void Start()
        {
            started = true;
            MyAPIGateway.Multiplayer.RegisterSecureMessageHandler(Protocol.Channel, OnMessage);
            SendHello();
        }

        public static void Stop()
        {
            if (started)
                MyAPIGateway.Multiplayer?.UnregisterSecureMessageHandler(
                    Protocol.Channel,
                    OnMessage
                );
            started = false;
            timedOut = false;
            Served = false;
            Grants = default;
            pending.Clear();
            pendingHide.Clear();
            revokedUntil.Clear();
        }

        private static void SendHello()
        {
            sentOptions = (Config.Current.RestoreToolbars, Config.Current.HandleSubgrids);
            helloUtc = DateTime.UtcNow;
            Send(
                Protocol.Write(
                    MessageType.Hello,
                    w =>
                    {
                        w.Write(Protocol.Version);
                        w.Write(sentOptions.RestoreToolbars);
                        w.Write(sentOptions.HandleSubgrids);
                    }
                )
            );
        }

        private static void Send(byte[] message) =>
            MyAPIGateway.Multiplayer.SendMessageToServer(Protocol.Channel, message, true);

        // --- editing ---------------------------------------------------------------

        // The grids arrive for copy, cut and blueprint; errors are shown to the player
        public static void RequestEdit(
            EditOperation operation,
            MyCubeGrid grid,
            BoundingBoxI box,
            bool includeIntersectingBlocks,
            Vector3I? originBlockMin,
            string sizeText,
            Action<List<MyObjectBuilder_CubeGrid>> onGrids = null
        )
        {
            var request = new EditRequest
            {
                RequestId = ++nextRequestId,
                Operation = operation,
                GridId = grid.EntityId,
                Box = box,
                IncludeIntersectingBlocks = includeIntersectingBlocks,
                OriginBlockMin = originBlockMin,
                SizeText = sizeText,
            };
            pending[request.RequestId] = new PendingEdit
            {
                Operation = operation,
                OnGrids = onGrids,
            };
            Send(Protocol.Write(MessageType.Edit, w => Protocol.WriteEdit(w, request)));
        }

        private static void OnResult(BinaryReader reader)
        {
            var requestId = reader.ReadInt32();
            var operation = (EditOperation)reader.ReadByte();
            var ok = reader.ReadBoolean();
            var error = reader.ReadString();
            var partCount = reader.ReadInt32();
            if (!pending.TryGetValue(requestId, out var edit))
                return;

            if (!ok)
            {
                pending.Remove(requestId);
                MyAPIGateway.Utilities.ShowMessage("Sections", $"{operation} failed: {error}");
                return;
            }

            if (partCount == 0)
            {
                pending.Remove(requestId);
                if (operation == EditOperation.ClearReferences)
                    MyAPIGateway.Utilities.ShowMessage(
                        "Sections",
                        "Block reference data has been cleared from this grid and all connected subgrids"
                    );
                return;
            }
            edit.Parts = new byte[partCount][];
        }

        private static void OnPart(BinaryReader reader)
        {
            var requestId = reader.ReadInt32();
            var index = reader.ReadInt32();
            var bytes = reader.ReadBytes(reader.ReadInt32());
            if (
                !pending.TryGetValue(requestId, out var edit)
                || edit.Parts == null
                || index < 0
                || index >= edit.Parts.Length
                || edit.Parts[index] != null
            )
                return;

            edit.Parts[index] = bytes;
            if (++edit.Received < edit.Parts.Length)
                return;

            pending.Remove(requestId);
            var grids = GridTransfer.Deserialize(edit.Parts.SelectMany(p => p).ToArray());
            edit.OnGrids?.Invoke(grids);
        }

        // --- cutaways --------------------------------------------------------------

        public static void QueueHide(MySlimBlock block, bool hide)
        {
            var grid = block?.CubeGrid;
            if (!CanHideCollision || grid == null)
                return;
            if (!pendingHide.TryGetValue(grid.EntityId, out var cells))
                pendingHide[grid.EntityId] = cells = new Dictionary<Vector3I, bool>();
            cells[block.Min] = hide;
        }

        private static void FlushHide()
        {
            if (!CanHideCollision)
            {
                pendingHide.Clear();
                return;
            }

            foreach (var entry in pendingHide)
            {
                foreach (var hide in new[] { false, true })
                {
                    var positions = entry
                        .Value.Where(c => c.Value == hide)
                        .Select(c => c.Key)
                        .ToList();
                    for (var i = 0; i < positions.Count; i += Protocol.MaxHidePositions)
                    {
                        var chunk = positions.Skip(i).Take(Protocol.MaxHidePositions).ToList();
                        Send(
                            Protocol.Write(
                                MessageType.Hide,
                                w =>
                                {
                                    w.Write(entry.Key);
                                    w.Write(hide);
                                    Protocol.WritePositions(w, chunk);
                                }
                            )
                        );
                    }
                }
            }
            pendingHide.Clear();
        }

        private static void OnRevoke(BinaryReader reader)
        {
            var gridId = reader.ReadInt64();
            var reason = reader.ReadString();
            Log.Info(
                $"The server restored the blocks of {(gridId == 0 ? "all grids" : gridId.ToString())}: {reason}"
            );
            MyAPIGateway.Utilities.ShowMessage("Sections", $"Cutaway removed: {reason}");
            if (gridId == 0)
            {
                Logic.Cutaway.Restore(force: true);
                return;
            }
            revokedUntil[gridId] = DateTime.UtcNow.AddSeconds(RevokedSeconds);
            if (MyEntities.GetEntityByIdOrDefault(gridId) is MyCubeGrid grid)
                Logic.Cutaway.Restore(grid, stopAutomatic: false);
        }

        // --- messages --------------------------------------------------------------

        private static void OnMessage(ushort channel, byte[] message, ulong sender, bool fromServer)
        {
            if (!fromServer || message == null || message.Length == 0)
                return;

            try
            {
                var reader = Protocol.Read(message, out var type);
                switch (type)
                {
                    case MessageType.Welcome:
                        OnWelcome(reader);
                        break;
                    case MessageType.Grants:
                        Grants = Protocol.ReadGrants(reader);
                        Log.Info($"Grants: {Grants}");
                        break;
                    case MessageType.Result:
                        OnResult(reader);
                        break;
                    case MessageType.Part:
                        OnPart(reader);
                        break;
                    case MessageType.Revoke:
                        OnRevoke(reader);
                        break;
                }
            }
            catch (Exception e)
            {
                Log.Warning($"A message from the server could not be handled: {e}");
            }
        }

        private static void OnWelcome(BinaryReader reader)
        {
            var version = reader.ReadInt32();
            var served = reader.ReadBoolean();
            var reason = reader.ReadString();
            if (!served)
            {
                Served = false;
                Log.Info(
                    $"Not served by the server's Sections companion (protocol {version}): {reason}"
                );
                return;
            }

            Grants = Protocol.ReadGrants(reader);
            Served = true;
            Log.Info($"Served by the server's Sections companion: {Grants}");

            // The server starts over after a Hello, it needs every block hidden without collision
            pendingHide.Clear();
            foreach (var block in Logic.Cutaway.CollisionHiddenBlocks())
                QueueHide(block, true);
        }
    }
}
