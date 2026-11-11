"""Synthetic laps with braking zones known in closed form.

No real telemetry in the test suite: every assertion compares against a
value computed by hand. Checks against real data need the network and
live in examples/, out of CI on purpose (same rule as apex-trace).
"""

import numpy as np
import pandas as pd
import pytest
from apextrace.lap import Lap
from scipy.integrate import cumulative_trapezoid

G = 9.81
STEP = 5.0


def constant_decel_profile(dist, v_top, corners, accel_g=1.0, hold=20.0):
    """Speed [km/h] for straights at v_top joined by constant-g stops.

    corners: iterable of (brake_point [m], v_min [km/h], decel_g). Each
    stop follows v^2 = v0^2 - 2 a s exactly, holds v_min for `hold`
    metres (so the minimum lands on the grid instead of between two
    points of a sharp V), then accelerates back at accel_g to v_top.
    """
    v_top_ms = v_top / 3.6
    v = np.full(dist.size, v_top_ms)
    for brake_point, v_min, decel_g in corners:
        v_min_ms = v_min / 3.6
        a = decel_g * G
        d_stop = (v_top_ms**2 - v_min_ms**2) / (2 * a)
        s = dist - brake_point
        braking = (s >= 0) & (s <= d_stop)
        v[braking] = np.sqrt(v_top_ms**2 - 2 * a * s[braking])
        v[(s > d_stop) & (s <= d_stop + hold)] = v_min_ms
        s_out = s - d_stop - hold
        accel = s_out > 0
        v_out = np.sqrt(v_min_ms**2 + 2 * accel_g * G * s_out[accel])
        v[accel] = np.minimum(v[accel], v_out)
    return v * 3.6


@pytest.fixture
def make_lap():
    """Factory: a self-consistent Lap from distance-indexed channels."""

    def _make(dist, speed, throttle, brake, label="synthetic") -> Lap:
        data = pd.DataFrame(
            {
                "Distance": dist,
                "Time": cumulative_trapezoid(3.6 / speed, dist, initial=0.0),
                "Speed": speed,
                "Throttle": throttle,
                "Brake": brake,
                "Gear": np.full(dist.size, 8),
            }
        )
        return Lap(data=data, label=label, source="synthetic")

    return _make


@pytest.fixture
def grid():
    return np.arange(0.0, 3000.0 + STEP, STEP)
