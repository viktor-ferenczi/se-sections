using PluginSdk.Config;
using VRage.Game.ModAPI;

namespace ServerPlugin;

[Section("access", caption: "Access")]
[Section("limits", caption: "Limits")]
[Section("debug", caption: "Diagnostics")]
public class SectionsServerConfig : PluginConfig
{
    [EnumOption(
        "Lowest game access level allowed to copy, cut, delete and blueprint sections",
        Parent = "access"
    )]
    public MyPromoteLevel EditAccessLevel
    {
        get;
        set => SetField(ref field, value);
    } = MyPromoteLevel.Admin;

    [EnumOption(
        "Lowest game access level allowed to remove collision with cutaways and auto-hide",
        Parent = "access"
    )]
    public MyPromoteLevel CutawayAccessLevel
    {
        get;
        set => SetField(ref field, value);
    } = MyPromoteLevel.Admin;

    [BoolOption(
        "Removing collision also needs a creative world or creative tools",
        Parent = "access"
    )]
    public bool CutawayNeedsCreative
    {
        get;
        set => SetField(ref field, value);
    } = true;

    [EnumOption(
        "Lowest game access level allowed to use grids the player does not own",
        Parent = "access"
    )]
    public MyPromoteLevel AnyGridAccessLevel
    {
        get;
        set => SetField(ref field, value);
    } = MyPromoteLevel.Admin;

    [IntOption(1, 10000000, "Most blocks a player may have without collision", Parent = "limits")]
    public int MaxHiddenBlocksPerPlayer
    {
        get;
        set => SetField(ref field, value);
    } = 100000;

    [BoolOption("Write Sections/status-players.json every second, for tests", Parent = "debug")]
    public bool DebugStatusFile
    {
        get;
        set => SetField(ref field, value);
    }
}
