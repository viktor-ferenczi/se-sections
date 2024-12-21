using System.Diagnostics;
using Sandbox.Game.Entities;
using Sandbox.Game.Entities.Blocks;

namespace ClientPlugin.Logic
{
    public readonly struct MechanicalConnection
    {
        public readonly MyMechanicalConnectionBlockBase BaseBlock;
        public readonly MyAttachableTopBlockBase TopBlock;

        public MyCubeGrid BaseGrid => BaseBlock.CubeGrid;
        public MyCubeGrid TopGrid => TopBlock.CubeGrid;

        public MechanicalConnection(MyMechanicalConnectionBlockBase baseBlock, MyAttachableTopBlockBase topBlock)
        {
            BaseBlock = baseBlock;
            TopBlock = topBlock;

            Debug.Assert(baseBlock != null);
            Debug.Assert(topBlock != null);

            Debug.Assert(BaseGrid != null);
            Debug.Assert(TopGrid != null);
        }

        public override int GetHashCode()
        {
            return (int)(BaseBlock.EntityId ^ TopBlock.EntityId);
        }
    }
}