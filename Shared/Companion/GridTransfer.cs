using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using VRage.Game;
using VRage.ObjectBuilders.Private;

namespace Shared.Companion
{
    // Grid builders as gzipped blueprint XML, the way they travel from the server to the client
    public static class GridTransfer
    {
        public static byte[] Serialize(List<MyObjectBuilder_CubeGrid> grids)
        {
            var blueprint = new MyObjectBuilder_ShipBlueprintDefinition
            {
                CubeGrids = grids.ToArray(),
            };
            using (var buffer = new MemoryStream())
            {
                using (var gzip = new GZipStream(buffer, CompressionLevel.Optimal))
                {
                    if (!MyObjectBuilderSerializerKeen.SerializeXML(gzip, blueprint))
                        throw new InvalidDataException("Serializing the grids failed");
                }
                return buffer.ToArray();
            }
        }

        public static List<MyObjectBuilder_CubeGrid> Deserialize(byte[] data)
        {
            using (var gzip = new GZipStream(new MemoryStream(data), CompressionMode.Decompress))
            {
                if (
                    !MyObjectBuilderSerializerKeen.DeserializeXML(
                        gzip,
                        out MyObjectBuilder_ShipBlueprintDefinition blueprint
                    )
                    || blueprint?.CubeGrids == null
                )
                    throw new InvalidDataException("Deserializing the grids failed");
                return blueprint.CubeGrids.ToList();
            }
        }

        public static List<byte[]> Split(byte[] data, int partBytes)
        {
            var parts = new List<byte[]>();
            for (var offset = 0; offset < data.Length; offset += partBytes)
            {
                var part = new byte[System.Math.Min(partBytes, data.Length - offset)];
                System.Array.Copy(data, offset, part, 0, part.Length);
                parts.Add(part);
            }
            return parts;
        }
    }
}
