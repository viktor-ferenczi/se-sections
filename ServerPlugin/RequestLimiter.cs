using System;
using System.Collections.Generic;

namespace ServerPlugin;

// A token bucket per player: each request costs tokens, the bucket refills over time.
// Knows nothing about the game. Copied from the Undo companion.
public sealed class RequestLimiter
{
    private readonly double size;
    private readonly double refillPerSecond;
    private readonly Dictionary<ulong, (double Tokens, DateTime Utc)> buckets =
        new Dictionary<ulong, (double, DateTime)>();

    public RequestLimiter(double size, double refillPerSecond)
    {
        this.size = size;
        this.refillPerSecond = refillPerSecond;
    }

    // False when the player has to wait; nothing is taken then
    public bool Take(ulong player, double cost, DateTime utcNow)
    {
        var (tokens, last) = buckets.TryGetValue(player, out var bucket) ? bucket : (size, utcNow);
        tokens = Math.Min(size, tokens + (utcNow - last).TotalSeconds * refillPerSecond);
        var allowed = tokens >= cost;
        buckets[player] = (allowed ? tokens - cost : tokens, utcNow);
        return allowed;
    }

    public void Clear() => buckets.Clear();
}
