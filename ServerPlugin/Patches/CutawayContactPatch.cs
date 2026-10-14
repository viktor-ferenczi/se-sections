using HarmonyLib;
using Havok;
using Sandbox.Engine.Physics;
using Sandbox.Game.Entities;
using Sandbox.Game.Entities.Character;
using Sandbox.Game.Entities.Cube;
using VRage.Game.Entity;
using VRageMath;

namespace ServerPlugin.Patches;

// Lets a player's character through the blocks that player hid with collision removal.
// The game does the same for the ladder a character climbs: it disables the contact
// points in the character's contact callback. The grid's shape stays whole, so every
// other character and body still collides with the blocks.
[HarmonyPatch(typeof(MyCharacter), "RigidBody_ContactPointCallback")]
public static class CutawayContactPatch
{
    private static bool Prefix(MyCharacter __instance, ref HkContactPointEvent value)
    {
        if (!Companion.HasHiddenBlocks(__instance.EntityId))
            return true;

        var bodyA = value.Base.BodyA?.GetBody();
        var bodyB = value.Base.BodyB?.GetBody();
        var other =
            bodyA?.Entity == __instance ? bodyB?.Entity as MyEntity : bodyA?.Entity as MyEntity;
        var otherIndex = bodyA?.Entity == __instance ? 1 : 0;

        var block = other switch
        {
            MyCubeGrid grid => BlockAtContact(__instance, grid, ref value, otherIndex),
            MyEntitySubpart subpart => BlockOfSubpart(subpart),
            _ => null,
        };
        if (!Companion.IsHiddenFor(__instance.EntityId, block))
            return true;

        // Skips the game's handling too: no footstep, sound or damage from a hidden block
        var properties = value.ContactProperties;
        properties.IsDisabled = true;
        return false;
    }

    // Armor shapes are merged into larger boxes, so the shape key names only one block of
    // a box. The cell behind the contact, seen from the character, is the block touched.
    // When there is none, the character is inside the box and the cell in front counts.
    private static MySlimBlock BlockAtContact(
        MyCharacter character,
        MyCubeGrid grid,
        ref HkContactPointEvent value,
        int gridBodyIndex
    )
    {
        var physics = grid.Physics;
        if (physics == null)
            return null;

        var point = physics.ClusterToWorld(value.ContactPoint.Position);
        Vector3D normal = value.ContactPoint.Normal;
        if (Vector3D.Dot(normal, point - character.PositionComp.WorldAABB.Center) < 0)
            normal = -normal;

        var step = normal * grid.GridSize * 0.25;
        var behind = grid.GetCubeBlock(grid.WorldToGridInteger(point + step));
        if (behind != null)
            return behind;
        var inFront = grid.GetCubeBlock(grid.WorldToGridInteger(point - step));
        if (inFront != null)
            return inFront;

        var shapeKey = value.GetShapeKey(gridBodyIndex);
        return shapeKey == uint.MaxValue ? null : physics.Shape?.GetBlockFromShapeKey(shapeKey);
    }

    // Door leaves and other moving parts have bodies of their own
    private static MySlimBlock BlockOfSubpart(MyEntity entity)
    {
        while (entity != null && !(entity is MyCubeBlock))
            entity = entity.Parent;
        return (entity as MyCubeBlock)?.SlimBlock;
    }
}
