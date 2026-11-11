using Sandbox.Game.Multiplayer;
using Sandbox.Game.World;
using Shared.Companion;
using VRage.Game.ModAPI;

namespace ClientPlugin.Companion
{
    // A lobby host serves its joined players' section editing the way the server
    // companion does, with the server's defaults: admins only. Collision removal is
    // not served, the joined players' cutaways stay visual only.
    public static class LobbyHost
    {
        private sealed class Options : ICompanionOptions
        {
            public MyPromoteLevel EditAccessLevel => MyPromoteLevel.Admin;
            public MyPromoteLevel CutawayAccessLevel => MyPromoteLevel.Admin;
            public bool CutawayNeedsCreative => true;
            public MyPromoteLevel AnyGridAccessLevel => MyPromoteLevel.Admin;
            public int MaxHiddenBlocksPerPlayer => 0;
            public bool DebugStatusFile => false;
        }

        private static readonly Options options = new Options();

        public static void Update()
        {
            if (
                !CompanionServer.Running
                && Sync.MultiplayerActive
                && Sync.IsServer
                && !Sync.IsDedicated
                && MySession.Static?.Ready == true
            )
                CompanionServer.Start(options, cutaways: false);
            CompanionServer.Update();
        }
    }
}
