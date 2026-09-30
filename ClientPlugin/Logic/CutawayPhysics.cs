namespace ClientPlugin.Logic
{
    internal static class CutawayPhysics
    {
        public static bool IsAllowed(bool multiplayer, bool host, bool friends) =>
            !multiplayer || (host && friends);
    }
}
