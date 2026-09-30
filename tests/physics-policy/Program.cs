using System;
using ClientPlugin.Logic;

var cases = new[]
{
    (Multiplayer: false, Host: false, Friends: false, Expected: true),
    (Multiplayer: false, Host: false, Friends: true, Expected: true),
    (Multiplayer: false, Host: true, Friends: false, Expected: true),
    (Multiplayer: false, Host: true, Friends: true, Expected: true),
    (Multiplayer: true, Host: false, Friends: false, Expected: false),
    (Multiplayer: true, Host: false, Friends: true, Expected: false),
    (Multiplayer: true, Host: true, Friends: false, Expected: false),
    (Multiplayer: true, Host: true, Friends: true, Expected: true),
};
foreach (var test in cases)
{
    if (CutawayPhysics.IsAllowed(test.Multiplayer, test.Host, test.Friends) != test.Expected)
        throw new Exception($"Wrong physics permission: {test}");
}
Console.WriteLine("PASS offline, friends host, and all other multiplayer roles");
