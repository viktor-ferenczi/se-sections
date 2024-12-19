using System.IO;
using Sandbox.Game.GUI;

namespace ClientPlugin.Logic
{
    public static class Constants
    {
        public static readonly string LocalTempDir = Path.Combine(Path.GetTempPath(), "SpaceEngineers", Plugin.Name);

        static Constants()
        {
            if (!Directory.Exists(LocalTempDir))
                Directory.CreateDirectory(LocalTempDir);
        }
    }
}