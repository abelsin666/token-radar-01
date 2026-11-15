#!/usr/bin/env python3
"""
Token Launch Radar — detects new token launches on Solana.

Reads JSON lines from stdin (token launch events), filters and scores them,
outputs scored tokens as JSON lines.

Strategy:
- Filter by volume, liquidity, holder count
- Score: volume z-score, velocity, unique holders, sniper detection
- Output: ranked list of tokens likely to pump
"""

import json
import sys
import math
from collections import deque


def zscore(values):
    if len(values) < 2:
        return 0.0
    m = sum(values) / len(values)
    var = sum((x - m) ** 2 for x in values) / len(values)
    std = math.sqrt(var) if var > 0 else 1.0
    return (values[-1] - m) / std


def main():
    volume_hist = deque(maxlen=60)
    velocity_hist = deque(maxlen=60)
    scored = []

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        token = event.get('mint', 'unknown')
        volume = event.get('volume_usd', 0.0)
        liquidity = event.get('liquidity_usd', 0.0)
        holders = event.get('unique_holders', 0)
        age_minutes = event.get('age_minutes', 0)

        volume_hist.append(volume)
        velocity_hist.append(event.get('trades_per_min', 0))

        vol_z = zscore(list(volume_hist))
        vel_z = zscore(list(velocity_hist))

        # Scoring: weighted combination
        score = 0.0
        score += max(0, vol_z) * 0.4
        score += max(0, vel_z) * 0.3
        score += min(holders / 100, 1.0) * 0.2
        score += min(liquidity / 10000, 1.0) * 0.1

        # Sniper penalty: high volume + few holders = likely sniper
        if volume > 100000 and holders < 5:
            score *= 0.3

        if score > 0.3:
            scored.append({
                'mint': token,
                'score': round(score, 4),
                'volume_z': round(vol_z, 2),
                'velocity_z': round(vel_z, 2),
                'holders': holders,
                'liquidity': round(liquidity, 2),
                'age_min': age_minutes,
                'signal': 'watch' if score < 0.5 else 'strong'
            })

        print(json.dumps({
            'event': token,
            'score': round(score, 4),
            'volume_z': round(vol_z, 2),
            'velocity_z': round(vel_z, 2),
            'holders': holders,
            'signal': 'watch' if score < 0.5 else 'strong' if score < 0.7 else 'pump',
        }), flush=True)


if __name__ == '__main__':
    main()
