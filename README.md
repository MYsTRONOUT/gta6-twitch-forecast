# gta6-twitch-forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/MYsTRONOUT/gta6-twitch-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/MYsTRONOUT/gta6-twitch-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecasts Grand Theft Auto VI's launch-day Twitch concurrent viewers hour by hour (hours 2–24, five quantiles each) from the hour-1 print and the launch-day curves of past big game launches.

## Run it

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

The grader runs it as `python3 /bot/main.py` (Python 3.13, standard library only, no network). It reads every `<id>.in` in the input directory and writes one `<id>.out` per case.

## How it works

Launch-day Twitch curves are driven by a midnight-local unlock rolling across time zones plus evening viewing peaks, so the *shape* of the curve across UTC hours is largely shared between big console launches, while the *scale* is set by the hour-1 print. The program therefore forecasts ratios to hour 1, not absolute counts:

1. For every comparable launch, take its release-day hourly viewers as log-ratios to its own hour-1 print.
2. Drop comparables that are not clean midnight-local console launches (kit tiers `early-access-contaminated`, `weak`, `target-history`).
3. Keep only comparables whose own hour-1 print is within a factor of 5 of this case's — hour 1 separates the pre-unlock regime (tiny prints, ratios in the hundreds) from the already-live regime (large prints, ratios near 1–3).
4. Per hour, the median is hour 1 × exp(mean log-ratio) with a light 5% trim; the outer quantiles are the empirical quantiles of the same log-ratios, shrunk 30% toward the centre.

Practice score (mean pinball loss on the log scale, lower is better): **0.162** across the four practice launches (Wolverine 0.200, Red Dead Redemption 2 0.125, God of War Ragnarök 0.115, Spider-Man 2 0.210), against **0.387** for the house persistence baseline.

---

<sub>Entered on [make.fun](https://make.fun/?ref=86f2bh8y&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
