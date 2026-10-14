using System;
using System.IO;
using System.Reflection;
using HarmonyLib;
using PluginSdk.Config;
using Sandbox.Game.World;
using Shared;
using VRage.FileSystem;
using VRage.Plugins;

// Define assembly version when compiled by Magnetar
#if !LOCAL_BUILD
[assembly: AssemblyVersion("1.5.0.0")]
[assembly: AssemblyFileVersion("1.5.0.0")]

#endif

namespace ServerPlugin;

// The Sections companion for a dedicated server. The work is in Companion and the patches.
// ReSharper disable once UnusedType.Global
public class Plugin : IPlugin
{
    private const string ConfigFileName = Log.Name + ".cfg";
    private static bool failed;

    public static SectionsServerConfig Config { get; private set; }

    [System.Runtime.CompilerServices.MethodImpl(
        System.Runtime.CompilerServices.MethodImplOptions.NoInlining
    )]
    public void Init(object gameInstance)
    {
        var path = Path.Combine(MyFileSystem.UserDataPath, ConfigFileName);
        try
        {
            Config = ConfigStorage.LoadXml<SectionsServerConfig>(path);
        }
        catch (Exception e)
        {
            Config = new SectionsServerConfig();
            Log.Warning($"Loading {path} failed, using the defaults: {e.Message}");
        }

        new Harmony(Log.Name).PatchAll(Assembly.GetExecutingAssembly());
        Log.Info("Companion loaded");
    }

    public void Dispose()
    {
        // IMPORTANT: Do NOT call harmony.UnpatchAll() here! It may break other plugins.
    }

    public void Update()
    {
        if (failed)
            return;

        try
        {
            // Magnetar initializes plugins after the world loaded, too late for a
            // session component of the plugin to be registered
            if (!Companion.Running && MySession.Static?.Ready == true)
                Companion.Start();
            Companion.Update();
        }
        catch (Exception e)
        {
            failed = true;
            Log.Error($"Update failed, the companion stops: {e}");
        }
    }
}
