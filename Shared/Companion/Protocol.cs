using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using VRageMath;

namespace Shared.Companion
{
    // What the client plugin and a dedicated server running the companion say to each
    // other, see the README. Mod messages on one channel; the server takes the sender's
    // Steam id from the network, never from the message.
    public enum MessageType : byte
    {
        // Client: the protocol version and the player's options
        Hello = 1,

        // Server: whether it serves this client, with the grants
        Welcome = 2,

        // Server: the player's grants changed
        Grants = 3,

        // Client: a section operation on a grid
        Edit = 4,

        // Server: the answer to an edit, the grid builders follow in parts
        Result = 5,

        // Server: a part of the gzipped grid builders of a result
        Part = 6,

        // Client: blocks it hid or showed with collision removal
        Hide = 7,

        // Server: the client must show the blocks of a grid (0: all grids) again
        Revoke = 8,
    }

    public enum EditOperation : byte
    {
        Copy = 1,
        Cut = 2,
        Delete = 3,
        Blueprint = 4,
        ClearReferences = 5,
    }

    // What the server lets a player do, decided on the server
    public struct Grants : IEquatable<Grants>
    {
        public bool Edit;
        public bool Cutaway;
        public bool AnyGrid;

        public bool Equals(Grants other) =>
            Edit == other.Edit && Cutaway == other.Cutaway && AnyGrid == other.AnyGrid;

        public override bool Equals(object obj) => obj is Grants other && Equals(other);

        public override int GetHashCode() => (Edit ? 1 : 0) | (Cutaway ? 2 : 0) | (AnyGrid ? 4 : 0);

        public override string ToString() => $"edit {Edit}, cutaway {Cutaway}, any grid {AnyGrid}";
    }

    public struct EditRequest
    {
        public int RequestId;
        public EditOperation Operation;
        public long GridId;
        public BoundingBoxI Box;
        public bool IncludeIntersectingBlocks;
        public Vector3I? OriginBlockMin;
        public string SizeText;
    }

    public static class Protocol
    {
        // A channel of its own among the mod message ids (Undo uses 48771)
        public const ushort Channel = 48772;

        // Raised when a message changes in a way the other side would misread
        public const int Version = 1;

        // Larger client messages are dropped unread
        public const int MaxClientMessageBytes = 65536;

        // Block positions in one Hide message, so it stays under the limit above
        public const int MaxHidePositions = 4000;

        // Grid builders go to the client in parts of this size
        public const int PartBytes = 60000;

        public const int MaxSizeTextLength = 32;

        public static byte[] Write(MessageType type, Action<BinaryWriter> body = null)
        {
            using (var buffer = new MemoryStream())
            {
                using (var writer = new BinaryWriter(buffer, Encoding.UTF8))
                {
                    writer.Write((byte)type);
                    body?.Invoke(writer);
                }
                return buffer.ToArray();
            }
        }

        public static BinaryReader Read(byte[] message, out MessageType type)
        {
            var reader = new BinaryReader(new MemoryStream(message), Encoding.UTF8);
            type = (MessageType)reader.ReadByte();
            return reader;
        }

        public static void WriteGrants(BinaryWriter writer, Grants grants)
        {
            writer.Write(grants.Edit);
            writer.Write(grants.Cutaway);
            writer.Write(grants.AnyGrid);
        }

        public static Grants ReadGrants(BinaryReader reader) =>
            new Grants
            {
                Edit = reader.ReadBoolean(),
                Cutaway = reader.ReadBoolean(),
                AnyGrid = reader.ReadBoolean(),
            };

        public static void WriteVector(BinaryWriter writer, Vector3I v)
        {
            writer.Write(v.X);
            writer.Write(v.Y);
            writer.Write(v.Z);
        }

        public static Vector3I ReadVector(BinaryReader reader) =>
            new Vector3I(reader.ReadInt32(), reader.ReadInt32(), reader.ReadInt32());

        public static void WriteEdit(BinaryWriter writer, EditRequest request)
        {
            writer.Write(request.RequestId);
            writer.Write((byte)request.Operation);
            writer.Write(request.GridId);
            WriteVector(writer, request.Box.Min);
            WriteVector(writer, request.Box.Max);
            writer.Write(request.IncludeIntersectingBlocks);
            writer.Write(request.OriginBlockMin.HasValue);
            if (request.OriginBlockMin.HasValue)
                WriteVector(writer, request.OriginBlockMin.Value);
            writer.Write(request.SizeText ?? "");
        }

        public static EditRequest ReadEdit(BinaryReader reader)
        {
            var request = new EditRequest
            {
                RequestId = reader.ReadInt32(),
                Operation = (EditOperation)reader.ReadByte(),
                GridId = reader.ReadInt64(),
                Box = new BoundingBoxI(ReadVector(reader), ReadVector(reader)),
                IncludeIntersectingBlocks = reader.ReadBoolean(),
            };
            if (reader.ReadBoolean())
                request.OriginBlockMin = ReadVector(reader);
            var sizeText = reader.ReadString();
            request.SizeText =
                sizeText.Length > MaxSizeTextLength
                    ? sizeText.Substring(0, MaxSizeTextLength)
                    : sizeText;
            return request;
        }

        public static void WritePositions(BinaryWriter writer, ICollection<Vector3I> positions)
        {
            writer.Write(positions.Count);
            foreach (var position in positions)
                WriteVector(writer, position);
        }

        public static List<Vector3I> ReadPositions(BinaryReader reader)
        {
            var count = reader.ReadInt32();
            if (count < 0 || count > MaxHidePositions)
                throw new InvalidDataException($"{count} block positions");
            var positions = new List<Vector3I>(count);
            for (var i = 0; i < count; i++)
                positions.Add(ReadVector(reader));
            return positions;
        }
    }
}
