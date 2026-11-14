"""Estimators for the race analysis. Pure functions on zone tables."""

import numpy as np
import pandas as pd

STINT = ["session", "driver", "stint", "corner"]


def cluster_bootstrap(frame: pd.DataFrame, stat, by: str = "session", n: int = 500):
    """95 % interval of stat(frame), resampling whole groups of `by`.

    Laps of one race share conditions, so they are not independent
    draws; resampling races instead of rows keeps the interval honest.
    """
    rng = np.random.default_rng(0)
    groups = [g for _, g in frame.groupby(by)]
    draws = []
    for _ in range(n):
        pick = rng.integers(0, len(groups), len(groups))
        draws.append(stat(pd.concat([groups[i] for i in pick])))
    lo, hi = np.nanpercentile(np.array(draws, dtype=float), [2.5, 97.5], axis=0)
    return stat(frame), lo, hi


def lap_pairs(zones: pd.DataFrame, max_jump: float = 50.0) -> pd.DataFrame:
    """Brake-point change between consecutive clean laps, same stint and corner.

    Returns one row per pair with d (metres, later lap minus earlier),
    noise (the sampling variance of d) and the group keys. Differences
    between consecutive laps cancel slow drifts such as tyre wear.
    Pairs that jump more than max_jump are left out: a lock-up or a
    defended overtake, not the driver's normal scatter.

    Sampling variance: a brake point sits at the midpoint between the
    last raw sample without brake and the first with it, so its error
    is uniform within +/- u (bp_uncertainty_m) and has variance u^2/3.
    """
    z = zones.sort_values([*STINT, "lap_number"])
    same = (z[STINT] == z[STINT].shift()).all(axis=1) & (z["lap_number"].diff() == 1)
    d = z["bp_before_mark"].diff()
    u2 = z["bp_uncertainty_m"] ** 2 / 3.0
    out = z[STINT + ["team"]].copy()
    out["d"] = d
    out["noise"] = u2 + u2.shift()
    out = out[same & (d.abs() <= max_jump)]
    return out.dropna(subset=["d", "noise"])


def spread(pairs: pd.DataFrame) -> float:
    """Lap-to-lap standard deviation of the brake point [m], noise removed.

    var(d) = 2 sigma^2 + noise, so sigma^2 = (mean(d^2) - mean(noise)) / 2.
    What is left is everything that moves a race brake point from one
    lap to the next: the driver, but also traffic and energy management.
    Odometer error is not a large part of it: at Monza the result is the
    same for the first corner of the lap and the last (11.2 and 10.5 m),
    and the same when measured back from the apex instead of the line.
    """
    var = (np.mean(pairs["d"] ** 2) - np.mean(pairs["noise"])) / 2.0
    return float(np.sqrt(max(var, 0.0)))


def stint_slopes(zones: pd.DataFrame, value: str = "bp_before_mark") -> np.ndarray:
    """Change of `value` per lap of tyre age and per lap of race distance.

    Least squares on value ~ tyre_age + lap_number with a separate level
    for every (session, driver, corner), done by subtracting group means
    from all three columns. Tyre age and lap number move together inside
    a stint; the pit stop, which resets one and not the other, is what
    separates them. Returns [per_tyre_lap, per_race_lap].
    """
    keys = ["session", "driver", "corner"]
    cols = [value, "tyre_age", "lap_number"]
    z = zones.dropna(subset=cols)
    centred = z[cols] - z.groupby(keys)[cols].transform("mean")
    x = centred[["tyre_age", "lap_number"]].to_numpy(dtype=float)
    y = centred[value].to_numpy(dtype=float)
    coef, *_ = np.linalg.lstsq(x, y, rcond=None)
    return coef


def race_margin(quali: pd.DataFrame, race: pd.DataFrame, min_laps: int = 5):
    """Qualifying against race, per driver and corner.

    quali needs bp_scaled: the qualifying brake point measured the same
    way as the race one (scaled marks). Returns one row per (track,
    driver, corner) with margin_m (race median minus qualifying, positive
    = brakes earlier in the race) and the change in entry speed, minimum
    speed and peak deceleration.
    """
    keys = ["track", "driver", "corner"]
    r = race.groupby(keys).agg(
        team=("team", "first"),
        laps=("lap_number", "size"),
        bp_r=("bp_before_mark", "median"),
        entry_r=("entry_speed", "median"),
        vmin_r=("min_speed", "median"),
        peak_r=("peak_decel_g", "median"),
    )
    q = quali.set_index(keys)[["bp_scaled", "entry_speed", "min_speed", "peak_decel_g"]]
    m = r[r["laps"] >= min_laps].join(q, how="inner")
    m["margin_m"] = m["bp_r"] - m["bp_scaled"]
    m["entry_delta"] = m["entry_r"] - m["entry_speed"]
    m["vmin_delta"] = m["vmin_r"] - m["min_speed"]
    m["peak_delta"] = m["peak_r"] - m["peak_decel_g"]
    return m.reset_index()
