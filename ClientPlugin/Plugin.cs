using System;
using System.Reflection;
using ClientPlugin.Logic;
using ClientPlugin.Settings;
using ClientPlugin.Settings.Layouts;
using HarmonyLib;
using Sandbox.Game.World;
using Sandbox.Graphics.GUI;
using VRage.Plugins;

namespace ClientPlugin
{
    // ReSharper disable once UnusedType.Global
    public class Plugin : IPlugin, IDisposable
    {
        public const string Name = "Sections";
        public static Plugin Instance { get; private set; }
        private SettingsGenerator settingsGenerator;

        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public void Init(object gameInstance)
        {
            Instance = this;
            Instance.settingsGenerator = new SettingsGenerator();

            // TODO: Put your one time initialization code here.
            Harmony harmony = new Harmony(Name);
            harmony.PatchAll(Assembly.GetExecutingAssembly());

            MySession.OnLoading += OnLoadingSession;
            MySession.OnUnloading += OnUnloadingSession;
        }

        public void Dispose()
        {
            MySession.OnLoading -= OnLoadingSession;
            MySession.OnUnloading -= OnUnloadingSession;

            Instance = null;
        }

        private void OnLoadingSession()
        {
            ModStorage.RegisterModStorageComponentDefinition();
        }

        private void OnUnloadingSession()
        {
            Logic.Logic.Static.Reset();
        }

        public void Update()
        {
            // TODO: Put your update code here. It is called on every simulation frame!
        }

        // ReSharper disable once UnusedMember.Global
        public void OpenConfigDialog()
        {
            Instance.settingsGenerator.SetLayout<Simple>();
            MyGuiSandbox.AddScreen(Instance.settingsGenerator.Dialog);
        }

        //TODO: Uncomment and use this method to load asset files
        /*public void LoadAssets(string folder)
        {

        }*/
    }
}