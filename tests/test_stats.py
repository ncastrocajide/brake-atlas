import numpy as np
import pandas as pd

from brakeatlas.stats import lap_pairs, race_margin, spread, stint_slopes


def stint_table(rng, sigma, u, laps=4000, drift=0.0):
    """One long stint at one corner: true scatter sigma, sampling +/- u."""
    n = np.arange(laps)
    bp = 100.0 + drift * n + rng.normal(0.0, sigma, laps) + rng.uniform(-u, u, laps)
    return pd.DataFrame(
        {
            "session": 1,
            "driver": "AAA",
            "team": "T",
            "stint": 1,
            "corner": "T1",
            "lap_number": n + 2,
            "bp_before_mark": bp,
            "bp_uncertainty_m": u,
        }
    )


def test_spread_recovers_the_scatter_under_sampling_noise():
    rng = np.random.default_rng(1)
    # Sampling error (+/- 10 m) is larger than the driver's scatter (4 m);
    # the estimator still has to return about 4, not about 7.
    pairs = lap_pairs(stint_table(rng, sigma=4.0, u=10.0))
    assert abs(spread(pairs) - 4.0) < 0.4


def test_spread_ignores_a_steady_drift():
    rng = np.random.default_rng(2)
    pairs = lap_pairs(stint_table(rng, sigma=3.0, u=8.0, drift=0.5))
    assert abs(spread(pairs) - 3.0) < 0.4


def test_pairs_need_consecutive_laps():
    rng = np.random.default_rng(3)
    table = stint_table(rng, sigma=1.0, u=1.0, laps=10)
    table = table[table["lap_number"] != 6]  # a filtered lap splits the run
    assert len(lap_pairs(table)) == 7


def test_stint_slopes_separate_tyres_from_fuel():
    rng = np.random.default_rng(4)
    rows = []
    for driver, stop in (("AAA", 15), ("BBB", 30)):
        for lap in range(2, 51):
            age = lap if lap < stop else lap - stop
            rows.append((driver, lap, age, 120.0 + 0.30 * age - 0.10 * lap))
    z = pd.DataFrame(
        rows, columns=["driver", "lap_number", "tyre_age", "bp_before_mark"]
    )
    z["bp_before_mark"] += rng.normal(0.0, 0.5, len(z))
    z["session"], z["corner"] = 1, "T1"
    tyre, fuel = stint_slopes(z)
    assert abs(tyre - 0.30) < 0.02
    assert abs(fuel + 0.10) < 0.02


def test_race_margin_is_race_minus_qualifying():
    quali = pd.DataFrame(
        {
            "track": "X",
            "driver": "AAA",
            "corner": "T1",
            "bp_scaled": [100.0],
            "entry_speed": [320.0],
            "min_speed": [80.0],
            "peak_decel_g": [5.0],
        }
    )
    race = pd.DataFrame(
        {
            "track": "X",
            "driver": "AAA",
            "corner": "T1",
            "team": "T",
            "lap_number": range(2, 12),
            "bp_before_mark": 112.0,
            "entry_speed": 300.0,
            "min_speed": 75.0,
            "peak_decel_g": 4.0,
        }
    )
    m = race_margin(quali, race)
    assert m.loc[0, "margin_m"] == 12.0
    assert m.loc[0, "entry_delta"] == -20.0
