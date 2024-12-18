using VRageMath;

namespace ClientPlugin.Logic
{
    public static class Extensions
    {
        public static int IndexOfFirstNonzeroAxis(this Vector3I v)
        {
            if (v[0] != 0)
                return 0;
            if (v[1] != 0)
                return 1;
            if (v[2] != 0)
                return 2;
            return -1;
        }

        public static Vector3I GetClosestIntDirection(this Base6Directions.Direction[] closestDirections, Base6Directions.Direction direction)
        {
            return Base6Directions.IntDirections[(int)closestDirections[(int)direction]];
        }

        public static Base6Directions.Direction[] FindClosestDirectionsTo(this MatrixD matrix, MatrixD other)
        {
            var bestForward = Base6Directions.Direction.Right;
            var bestUp = Base6Directions.Direction.Up;
            var bestFit = double.NegativeInfinity;

            var otherForwardVector = other.Forward;
            var otherUpVector = other.Up;

            for (var forwardIndex = 0; forwardIndex < 6; forwardIndex++)
            {
                var forward = (Base6Directions.Direction)forwardIndex;
                var forwardFit = matrix.GetDirectionVector(forward).Dot(otherForwardVector);

                for (var upIndex = 0; upIndex < 6; upIndex++)
                {
                    var up = (Base6Directions.Direction)upIndex;

                    if (up == forward || up == Base6Directions.GetOppositeDirection(forward))
                        continue;

                    var upFit = matrix.GetDirectionVector(up).Dot(otherUpVector);
                    var fit = forwardFit + upFit;
                    if (fit > bestFit)
                    {
                        bestForward = forward;
                        bestUp = up;
                        bestFit = fit;
                    }
                }
            }

            var bestLeft = Base6Directions.GetLeft(bestUp, bestForward);
            return new Base6Directions.Direction[6]
            {
                bestForward,
                Base6Directions.GetOppositeDirection(bestForward),
                bestLeft,
                Base6Directions.GetOppositeDirection(bestLeft),
                bestUp,
                Base6Directions.GetOppositeDirection(bestUp),
            };
        }
    }
}