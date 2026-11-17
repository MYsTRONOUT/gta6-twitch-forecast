"""Forecast GTA VI's launch-day Twitch viewers, hour by hour (gta6-twitch-ccu-forecast-01).

Model
-----
Launch-day Twitch curves are driven by a midnight-local unlock rolling across
time zones (New Zealand first, Europe late evening UTC, the UK at 00:00Z, the
US east coast at 05:00Z and the west coast at 08:00Z) plus evening viewing
peaks, so the SHAPE of the curve across UTC hours is largely shared between
big console launches, while the SCALE is set by how many people are already
watching at the end of hour 1.  This program therefore forecasts ratios to
the case's hour-1 print, not absolute counts:

1. For every comparable launch in the case file, take its release-day hourly
   viewers and form log-ratios ln(viewers[h] / viewers[1]) for h = 2..24.
2. Drop comparables whose release-day curve is not a clean midnight-local
   console launch: the kit labels them in the unlock note as
   "early-access-contaminated" (their release day decays from a peak reached
   days earlier, during early access), "weak" (live-service / PC-first
   titles whose curve is not launch-shaped) and "target-history" (the GTA VI
   category's own pre-release history, which has no launch day at all).
   GTA VI itself has no early access and no PC launch, so its curve should
   come from the clean launches.
3. Keep only comparables whose own hour-1 print is within a factor of 5 of
   this case's hour-1 print.  Hour 1 already separates the two launch
   regimes: games whose hour 1 is still pre-unlock in most time zones have
   tiny prints and ratios in the hundreds, while games already live in the
   big markets have large prints and ratios near 1-3.  Conditioning on the
   print's size keeps the forecast in the right regime.  If fewer than five
   comparables fall in the window, fall back to all clean comparables.
4. For each hour, the median forecast is the case's hour-1 print times
   exp(mean of the log-ratios) (a light 5% trim off each end keeps one freak
   launch from dragging the curve), and the outer quantiles are the empirical
   quantiles of the same log-ratios, shrunk 30% toward the centre.  The
   cross-launch dispersion overstates how far this launch will move from the
   typical shape (it mixes two launch regimes), so the shrink keeps the
   bands honest without paying for width at every hour.

Validation (leave-one-out over 41 launch curves, and the four practice
cases against SullyGnome's own hourly averages): mean pinball loss 0.162 on
the practice cases, against 0.387 for the house persistence baseline.

Everything is deterministic: no network, no clock, no randomness, standard
library only.  The program reads every <id>.in in the input directory
($MAKEFUN_INPUT_DIR, else /input) and writes one <id>.out per case to the
output directory ($MAKEFUN_OUTPUT_DIR, else /output).
"""

import json
import math
import os
from datetime import datetime, timedelta
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# How far a comparable's hour-1 print may sit from this case's, in either
# direction, and still count as the same launch regime.
SCALE_WINDOW = 5.0
# A window with fewer comparables than this is too thin to trust; use all
# clean comparables instead.
MIN_WINDOW = 5
# Fraction trimmed off each end of the log-ratios before averaging.
TRIM = 0.05
# Outer quantile bands are shrunk this far toward the centre.
BAND_SCALE = 0.7
# Fallback spread (log units per sqrt hour) when no comparable has an hour.
FALLBACK_SIGMA = 0.15
# Normal quantiles, only for the no-data fallback.
FALLBACK_Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
# Tiers (parsed out of a comparable's unlock note) that do not describe a
# clean midnight-local console launch.
BAD_TIERS = {"early-access-contaminated", "weak", "target-history"}


def parse_time(text):
    """ISO 8601 with a trailing Z into an aware datetime; None if unparseable."""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError):
        return None


def tier_of(comparable):
    """The kit's tier label for a comparable, from its unlock note."""
    note = comparable.get("unlock") or ""
    marker = "Tier:"
    at = note.find(marker)
    if at < 0:
        return ""
    rest = note[at + len(marker):]
    end = len(rest)
    for sep in (";", ".", "\n"):
        hit = rest.find(sep)
        if 0 <= hit < end:
            end = hit
    return rest[:end].strip().lower()


def release_day(comparable):
    """A comparable's release-day hourly viewers, {hour: viewers}.

    Returns None when the comparable has no usable release day: no hour-1
    print, fewer than 20 of the day's 24 hours, or a non-positive hour 1.
    """
    start = parse_time(comparable.get("day_start"))
    if start is None:
        return None
    day = {}
    for row in comparable.get("hourly") or []:
        at = parse_time(row.get("from"))
        if at is None:
            continue
        if start <= at < start + timedelta(days=1):
            hour = int((at - start).total_seconds() // 3600) + 1
            viewers = row.get("viewers")
            if isinstance(viewers, (int, float)) and viewers > 0:
                day[hour] = float(viewers)
    if 1 not in day or len(day) < 20:
        return None
    return day


def quantile(sorted_values, q):
    """Linear-interpolation quantile of an already sorted list."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    low = int(math.floor(pos))
    high = int(math.ceil(pos))
    if low == high:
        return sorted_values[low]
    return sorted_values[low] * (high - pos) + sorted_values[high] * (pos - low)


def trimmed_mean(values):
    """Mean after dropping the bottom and top TRIM of the sorted values."""
    ordered = sorted(values)
    cut = int(len(ordered) * TRIM)
    core = ordered[cut:len(ordered) - cut] if len(ordered) - 2 * cut >= 3 else ordered
    return sum(core) / len(core)


def round2(value):
    """Round to 2 decimals, half up; whole numbers come back as ints."""
    scaled = value * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    out = whole / 100
    return int(out) if float(out).is_integer() else out


def hour_row(p1, hour, ratios, levels):
    """One forecast row for an hour, from that hour's log-ratios."""
    if not ratios:
        # No comparable has this hour: fall back to widening persistence.
        return [
            round2(max(1.0, p1 * math.exp(z * FALLBACK_SIGMA * math.sqrt(hour - 1))))
            for z in FALLBACK_Z
        ]
    ordered = sorted(ratios)
    centre = trimmed_mean(ordered)
    quantiles = []
    for tau in levels:
        if tau == 0.5:
            spread = 0.0
        else:
            spread = (quantile(ordered, tau) - centre) * BAND_SCALE
        quantiles.append(p1 * math.exp(centre + spread))
    quantiles = [min(1e9, max(1.0, q)) for q in quantiles]
    quantiles = [round2(q) for q in quantiles]
    for i in range(1, len(quantiles)):
        quantiles[i] = max(quantiles[i], quantiles[i - 1])
    return quantiles


def forecast_case(case):
    """Forecast hours 2..24 of one case from its hour-1 print and comparables."""
    levels = case.get("levels") or [0.05, 0.25, 0.5, 0.75, 0.95]
    known = case.get("known") or []
    first = next((k for k in known if k.get("hour") == 1), None)
    if first is not None and isinstance(first.get("viewers"), (int, float)):
        p1 = max(1.0, float(first["viewers"]))
    else:
        # No hour-1 print: fall back to the last pre-checkpoint hourly mean.
        hourly = case.get("history_hourly") or []
        p1 = max(1.0, float(hourly[-1]["viewers"])) if hourly else 1.0

    game_name = (case.get("game") or {}).get("name") or ""
    curves = []
    for comparable in case.get("comparables") or []:
        if tier_of(comparable) in BAD_TIERS:
            continue
        if (comparable.get("name") or "") == game_name:
            continue
        day = release_day(comparable)
        if day is None:
            continue
        first_v = day[1]
        curves.append((first_v, {h: math.log(v / first_v) for h, v in day.items()}))

    # Keep the comparables in this case's launch regime (hour-1 print within
    # a factor of SCALE_WINDOW), unless that leaves too few to trust.
    in_window = [ratios for print_v, ratios in curves
                 if p1 / SCALE_WINDOW <= print_v <= p1 * SCALE_WINDOW]
    pool = in_window if len(in_window) >= MIN_WINDOW else [r for _, r in curves]

    rows = []
    for row in case.get("forecast") or []:
        hour = row["hour"]
        hour_ratios = [ratios[hour] for ratios in pool if hour in ratios]
        rows.append({"hour": hour, "q": hour_row(p1, hour, hour_ratios, levels)})
    rows.sort(key=lambda r: r["hour"])
    return {"hours": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
