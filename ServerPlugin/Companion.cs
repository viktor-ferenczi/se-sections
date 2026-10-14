using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using Sandbox.Engine.Multiplayer;
using Sandbox.Game.Entities;
using Sandbox.Game.Entities.Cube;
using Sandbox.Game.World;
using Sandbox.ModAPI;
using Shared;
using Shared.Companion;
using Shared.Logic;
using VRage.FileSystem;
using VRage.Game.ModAPI;
using VRage.GameServices;
using VRageMath;

namespace ServerPlugin;

// A player who said Hello. The hidden blocks are the ones this player removed
// collision from; only this player's character passes through them.
internal sealed class ServedPlayer
{
    public readonly ulong SteamId;
    public bool RestoreToolbars = true;
    public bool HandleSubgrids = true;
    public Grants Grants;
    public long CharacterId;
    public Vector3D Position;

    public readonly Dictionary<MyCubeGrid, HashSet<MySlimBlock>> HiddenByGrid =
        new Dictionary<MyCubeGrid, HashSet<MySlimBlock>>();

    // Read by the contact callback, which may run on a physics worker thread
    public readonly ConcurrentDictionary<MySlimBlock, byte> Hidden =
        new ConcurrentDictionary<MySlimBlock, byte>();

    public ServedPlayer(ulong steamId) => SteamId = steamId;

    public void Add(MyCubeGrid grid, MySlimBlock block)
    {
        if (!HiddenByGrid.TryGetValue(grid, out var blocks))
            HiddenByGrid[grid] = blocks = new HashSet<MySlimBlock>();
        if (blocks.Add(block))
            Hidden[block] = 0;
    }

    public void Remove(MyCubeGrid grid, MySlimBlock block)
    {
        if (!HiddenByGrid.TryGetValue(grid, out var blocks) || !blocks.Remove(block))
            return;
        Hidden.TryRemove(block, out _);
        if (blocks.Count == 0)
            HiddenByGrid.Remove(grid);
    }

    public void RemoveGrid(MyCubeGrid grid)
    {
        if (!HiddenByGrid.TryGetValue(grid, out var blocks))
            return;
        foreach (var block in blocks)
            Hidden.TryRemove(block, out _);
        HiddenByGrid.Remove(grid);
    }

    public void Clear()
    {
        HiddenByGrid.Clear();
        Hidden.Clear();
    }
}

// The server half: answers the client plugin's requests after checking them for the
// sending player, and lets each player's character through the blocks that player hid.
// Nothing a client sends is trusted, the grants are decided here.
public static class Companion
{
    private const int CheckIntervalTicks = 60;
    private const int CharacterIntervalTicks = 10;

    private static readonly Dictionary<ulong, ServedPlayer> served =
        new Dictionary<ulong, ServedPlayer>();

    // Characters of the players with hidden blocks, swapped as a whole
    private static volatile Dictionary<long, ServedPlayer> byCharacter =
        new Dictionary<long, ServedPlayer>();

    private static readonly RequestLimiter limiter = new RequestLimiter(60, 30);
    private static readonly List<(MyCubeGrid Grid, ulong Paster)> pasted =
        new List<(MyCubeGrid, ulong)>();

    private static bool running;
    private static int tick;
    private static string lastStatus;

    public static bool Running => running;

    private static SectionsServerConfig Config => Plugin.Config;

    public static void Start()
    {
        if (running || MyMultiplayer.Static == null || MyAPIGateway.Multiplayer == null)
            return;

        running = true;
        served.Clear();
        byCharacter = new Dictionary<long, ServedPlayer>();
        limiter.Clear();
        pasted.Clear();
        lastStatus = null;

        // The block reference data would be dropped from the next save without it
        ModStorage.RegisterModStorageComponentDefinition();

        MyAPIGateway.Multiplayer.RegisterSecureMessageHandler(Protocol.Channel, OnMessage);
        MyMultiplayer.Static.ClientLeft += OnClientLeft;
        MySession.OnUnloading += Stop;
        Log.Info($"Serving section editing and cutaways, protocol {Protocol.Version}");
    }

    public static void Stop()
    {
        if (!running)
            return;

        running = false;
        MySession.OnUnloading -= Stop;
        MyAPIGateway.Multiplayer?.UnregisterSecureMessageHandler(Protocol.Channel, OnMessage);
        if (MyMultiplayer.Static != null)
            MyMultiplayer.Static.ClientLeft -= OnClientLeft;
        served.Clear();
        byCharacter = new Dictionary<long, ServedPlayer>();
        pasted.Clear();
    }

    // --- the contact callback ------------------------------------------------------

    public static bool IsHiddenFor(long characterId, MySlimBlock block) =>
        block != null
        && byCharacter.TryGetValue(characterId, out var player)
        && player.Hidden.ContainsKey(block);

    public static bool HasHiddenBlocks(long characterId) => byCharacter.ContainsKey(characterId);

    // --- frame loop ----------------------------------------------------------------

    public static void Update()
    {
        if (!running)
            return;

        RestorePastedReferences();

        tick++;
        if (tick % CharacterIntervalTicks == 0)
            UpdateCharacters();
        if (tick % CheckIntervalTicks == 0)
        {
            foreach (var player in served.Values)
                Check(player);
            UpdateCharacters();
            WriteStatus();
        }
    }

    private static void UpdateCharacters()
    {
        var characters = new Dictionary<long, ServedPlayer>();
        foreach (var player in served.Values)
        {
            var character = MySession.Static.Players.TryGetPlayerBySteamId(
                player.SteamId,
                out var gamePlayer
            )
                ? gamePlayer.Character
                : null;
            player.CharacterId = character?.EntityId ?? 0;
            player.Position = character?.PositionComp.GetPosition() ?? Vector3D.Zero;
            if (player.CharacterId != 0 && player.Hidden.Count != 0)
                characters[player.CharacterId] = player;
        }
        byCharacter = characters;
    }

    // Grants may change with promotion, creative tools or the world settings, and grid
    // access with ownership. Whatever the player lost goes, and the client is told.
    private static void Check(ServedPlayer player)
    {
        var grants = GrantsOf(player.SteamId);
        if (!grants.Equals(player.Grants))
        {
            player.Grants = grants;
            Send(
                player.SteamId,
                Protocol.Write(MessageType.Grants, w => Protocol.WriteGrants(w, grants))
            );
            Log.Info($"Grants of {player.SteamId} changed: {grants}");
        }

        if (!grants.Cutaway)
        {
            player.Clear();
            return;
        }

        foreach (var grid in player.HiddenByGrid.Keys.ToList())
        {
            if (grid.Closed || grid.MarkedForClose)
            {
                player.RemoveGrid(grid);
                continue;
            }
            if (!CanAccess(player, grid))
            {
                player.RemoveGrid(grid);
                Revoke(player, grid.EntityId, "you no longer have access to this grid");
                continue;
            }
            // Removed blocks, and blocks a split moved to another grid
            foreach (
                var block in player
                    .HiddenByGrid[grid]
                    .Where(b => b.CubeGrid != grid || grid.GetCubeBlock(b.Min) != b)
                    .ToList()
            )
                player.Remove(grid, block);
        }
    }

    // --- permissions ---------------------------------------------------------------

    private static Grants GrantsOf(ulong steamId)
    {
        var session = MySession.Static;
        var level = session.GetUserPromoteLevel(steamId);
        var creative = session.CreativeMode || session.CreativeToolsEnabled(steamId);
        return new Grants
        {
            Edit = level >= Config.EditAccessLevel && session.IsCopyPastingEnabledForUser(steamId),
            Cutaway =
                level >= Config.CutawayAccessLevel && (creative || !Config.CutawayNeedsCreative),
            AnyGrid = level >= Config.AnyGridAccessLevel,
        };
    }

    private static bool CanAccess(ServedPlayer player, MyCubeGrid grid)
    {
        if (
            grid == null
            || grid.Closed
            || grid.MarkedForClose
            || grid.Physics == null
            || grid.IsPreview
        )
            return false;
        if (player.Grants.AnyGrid)
            return true;
        var identityId = MySession.Static.Players.TryGetIdentityId(player.SteamId);
        return identityId != 0 && grid.BigOwners.Contains(identityId);
    }

    private static MyCubeGrid FindGrid(long gridId) =>
        MyEntities.GetEntityByIdOrDefault(gridId) as MyCubeGrid;

    // --- messages ------------------------------------------------------------------

    private static void Send(ulong steamId, byte[] message) =>
        MyAPIGateway.Multiplayer.SendMessageTo(Protocol.Channel, message, steamId, true);

    private static void Revoke(ServedPlayer player, long gridId, string reason) =>
        Send(
            player.SteamId,
            Protocol.Write(
                MessageType.Revoke,
                w =>
                {
                    w.Write(gridId);
                    w.Write(reason);
                }
            )
        );

    private static void OnClientLeft(ulong steamId, MyChatMemberStateChangeEnum _)
    {
        if (!served.Remove(steamId))
            return;
        UpdateCharacters();
        Log.Info($"{steamId} left, dropped its cutaways");
    }

    private static void OnMessage(ushort channel, byte[] message, ulong sender, bool fromServer)
    {
        if (fromServer || !running)
            return;

        if (
            message == null
            || message.Length == 0
            || message.Length > Protocol.MaxClientMessageBytes
        )
        {
            Log.Warning($"Dropped a message of {message?.Length ?? 0} bytes from {sender}");
            return;
        }

        try
        {
            var reader = Protocol.Read(message, out var type);
            if (!limiter.Take(sender, Cost(type), DateTime.UtcNow))
            {
                Log.Warning($"Dropped a {type} message from {sender}: too many requests");
                if (type == MessageType.Hide && served.TryGetValue(sender, out var limited))
                {
                    // The client's view of what collides is wrong now, start over
                    limited.Clear();
                    Revoke(limited, 0, "too many requests");
                }
                return;
            }

            if (type == MessageType.Hello)
            {
                OnHello(sender, reader);
                return;
            }

            // Everything else needs the handshake first
            if (!served.TryGetValue(sender, out var player))
                return;

            switch (type)
            {
                case MessageType.Edit:
                    OnEdit(player, Protocol.ReadEdit(reader));
                    break;
                case MessageType.Hide:
                    OnHide(player, reader);
                    break;
            }
        }
        catch (Exception e)
        {
            Log.Warning($"A message from {sender} could not be handled: {e}");
        }
    }

    private static double Cost(MessageType type) =>
        type switch
        {
            MessageType.Hello => 5,
            MessageType.Edit => 5,
            _ => 1,
        };

    private static void OnHello(ulong sender, BinaryReader reader)
    {
        var version = reader.ReadInt32();
        if (version != Protocol.Version)
        {
            Log.Info($"{sender} speaks Sections protocol {version}, not served");
            Send(
                sender,
                Protocol.Write(
                    MessageType.Welcome,
                    w =>
                    {
                        w.Write(Protocol.Version);
                        w.Write(false);
                        w.Write(
                            $"the server runs another version of Sections (protocol {Protocol.Version})"
                        );
                    }
                )
            );
            return;
        }

        if (!served.TryGetValue(sender, out var player))
            served[sender] = player = new ServedPlayer(sender);
        player.RestoreToolbars = reader.ReadBoolean();
        player.HandleSubgrids = reader.ReadBoolean();
        player.Grants = GrantsOf(sender);

        // A client says Hello again after a reload, it sends its hidden blocks again
        player.Clear();
        UpdateCharacters();

        var grants = player.Grants;
        Send(
            sender,
            Protocol.Write(
                MessageType.Welcome,
                w =>
                {
                    w.Write(Protocol.Version);
                    w.Write(true);
                    w.Write("");
                    Protocol.WriteGrants(w, grants);
                }
            )
        );
        Log.Info($"Serving {sender}: {grants}");
    }

    // --- editing -------------------------------------------------------------------

    private static void OnEdit(ServedPlayer player, EditRequest request)
    {
        string error;
        byte[] data = null;
        try
        {
            error = Edit(player, request, out data);
        }
        catch (Exception e)
        {
            Log.Error($"{request.Operation} for {player.SteamId} failed: {e}");
            error = "the server failed to do it, see its log";
        }

        var parts =
            data == null ? new List<byte[]>() : GridTransfer.Split(data, Protocol.PartBytes);
        Send(
            player.SteamId,
            Protocol.Write(
                MessageType.Result,
                w =>
                {
                    w.Write(request.RequestId);
                    w.Write((byte)request.Operation);
                    w.Write(error == null);
                    w.Write(error ?? "");
                    w.Write(parts.Count);
                }
            )
        );
        for (var i = 0; i < parts.Count; i++)
        {
            var index = i;
            Send(
                player.SteamId,
                Protocol.Write(
                    MessageType.Part,
                    w =>
                    {
                        w.Write(request.RequestId);
                        w.Write(index);
                        w.Write(parts[index].Length);
                        w.Write(parts[index]);
                    }
                )
            );
        }
    }

    // Null when done, otherwise the reason for the player
    private static string Edit(ServedPlayer player, EditRequest request, out byte[] data)
    {
        data = null;
        player.Grants = GrantsOf(player.SteamId);
        if (!player.Grants.Edit)
            return "section editing is not allowed for you on this server";

        var grid = FindGrid(request.GridId);
        if (!CanAccess(player, grid))
            return grid == null ? "the grid is gone" : "you don't own this grid";

        if (request.Operation == EditOperation.ClearReferences)
        {
            var grids = new MechanicalConnections(grid).IterGrids.ToList();
            if (grids.Any(g => !CanAccess(player, g)))
                return "you don't own all the connected grids";
            References.ClearBlockReferenceData(grid);
            Log.Info($"{player.SteamId} cleared the block reference data of {grid.DisplayName}");
            return null;
        }

        var box = new BoundingBoxI(
            Vector3I.Max(request.Box.Min, grid.Min),
            Vector3I.Min(request.Box.Max, grid.Max)
        );
        if (!box.IsValid)
            return "the selection is outside of the grid";

        var editor = new SectionEditor(
            grid,
            box,
            request.IncludeIntersectingBlocks,
            player.HandleSubgrids
        );
        if (player.RestoreToolbars)
            editor.BackupReferences();
        editor.Collect();
        if (editor.BlockMinPositions.Count == 0)
            return "no blocks are selected";

        var removes =
            request.Operation == EditOperation.Cut || request.Operation == EditOperation.Delete;
        if (removes && editor.Subgrids.Any(g => !CanAccess(player, g)))
            return "you don't own all the subgrids this would take along";

        if (request.Operation != EditOperation.Delete)
            data = GridTransfer.Serialize(
                editor.CreateGridBuilders(request.OriginBlockMin, request.SizeText)
            );
        if (removes)
            editor.Delete();

        Log.Info(
            $"{request.Operation} by {player.SteamId}: {editor.BlockMinPositions.Count} blocks and {editor.Subgrids.Count} subgrids of {grid.DisplayName}"
        );
        return null;
    }

    // --- cutaways ------------------------------------------------------------------

    private static void OnHide(ServedPlayer player, BinaryReader reader)
    {
        var gridId = reader.ReadInt64();
        var hide = reader.ReadBoolean();
        var positions = Protocol.ReadPositions(reader);

        player.Grants = GrantsOf(player.SteamId);
        if (!player.Grants.Cutaway)
        {
            if (hide)
                Revoke(player, 0, "removing collision is not allowed for you on this server");
            return;
        }

        var grid = FindGrid(gridId);
        if (grid == null)
            return;
        if (!CanAccess(player, grid))
        {
            player.RemoveGrid(grid);
            Revoke(player, gridId, "you don't own this grid");
            return;
        }

        foreach (var position in positions)
        {
            var block = grid.GetCubeBlock(position);
            if (block == null)
                continue;
            if (!hide)
                player.Remove(grid, block);
            else if (player.Hidden.Count < Config.MaxHiddenBlocksPerPlayer)
                player.Add(grid, block);
        }

        if (hide && player.Hidden.Count >= Config.MaxHiddenBlocksPerPlayer)
            Log.Warning($"{player.SteamId} reached the limit of hidden blocks");

        // The character map only lists players with hidden blocks
        if (
            player.CharacterId == 0
            || byCharacter.ContainsKey(player.CharacterId) != (player.Hidden.Count != 0)
        )
            UpdateCharacters();
    }

    // --- block references on paste -------------------------------------------------

    // The paste patches run inside the paste; references are restored on the next frame,
    // as the client plugin does offline
    public static void OnPasted(IEnumerable<MyCubeGrid> grids, ulong paster)
    {
        if (!running)
            return;
        foreach (var grid in grids)
            pasted.Add((grid, paster));
    }

    private static void RestorePastedReferences()
    {
        if (pasted.Count == 0)
            return;

        var grids = new HashSet<MyCubeGrid>();
        foreach (var (grid, paster) in pasted)
        {
            if (grid.Closed || grid.MarkedForClose || grid.Physics == null)
                continue;
            if (served.TryGetValue(paster, out var player) && !player.RestoreToolbars)
                continue;
            grids.Add(grid);
        }
        pasted.Clear();

        foreach (var grid in grids)
            new References(grid).Restore();
    }

    // --- status file for the tests -------------------------------------------------

    private static void WriteStatus()
    {
        if (!Config.DebugStatusFile)
            return;

        var json = new StringBuilder();
        json.Append("{\"players\":[");
        var first = true;
        foreach (var player in served.Values)
        {
            if (!first)
                json.Append(',');
            first = false;
            json.Append(
                $"{{\"steamId\":\"{player.SteamId}\",\"characterId\":\"{player.CharacterId}\","
            );
            var p = player.Position;
            json.Append(FormattableString.Invariant($"\"position\":[{p.X:F2},{p.Y:F2},{p.Z:F2}],"));
            json.Append(
                $"\"edit\":{Lower(player.Grants.Edit)},\"cutaway\":{Lower(player.Grants.Cutaway)},\"anyGrid\":{Lower(player.Grants.AnyGrid)},"
            );
            json.Append("\"hidden\":{");
            var firstGrid = true;
            foreach (var entry in player.HiddenByGrid)
            {
                if (!firstGrid)
                    json.Append(',');
                firstGrid = false;
                json.Append($"\"{entry.Key.EntityId}\":[");
                json.Append(
                    string.Join(",", entry.Value.Select(b => $"[{b.Min.X},{b.Min.Y},{b.Min.Z}]"))
                );
                json.Append(']');
            }
            json.Append("}}");
        }
        json.Append("]}");

        var status = json.ToString();
        if (status == lastStatus)
            return;
        lastStatus = status;

        try
        {
            var folder = Path.Combine(MyFileSystem.UserDataPath, Log.Name);
            Directory.CreateDirectory(folder);
            var path = Path.Combine(folder, "status-players.json");
            File.WriteAllText(path + ".tmp", status);
            File.Copy(path + ".tmp", path, true);
            File.Delete(path + ".tmp");
        }
        catch (Exception e)
        {
            Log.Warning($"Writing the status file failed: {e.Message}");
        }
    }

    private static string Lower(bool value) => value ? "true" : "false";
}
