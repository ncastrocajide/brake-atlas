from datetime import UTC, datetime, timedelta

import numpy as np

from brakeatlas.openf1 import load_lap

T0 = datetime(2026, 9, 5, 14, 0, tzinfo=UTC)


class FakeClient:
    """Serves a 20 s lap at constant 216 km/h (60 m/s), 4 Hz."""

    def __init__(self, frozen=()):
        self.frozen = frozen

    def get(self, endpoint, **params):
        rows = []
        for i in range(-8, 88):
            t = i * 0.25
            row = {"date": (T0 + timedelta(seconds=t)).isoformat()}
            if endpoint == "car_data":
                bad = self.frozen[0] <= t <= self.frozen[1] if self.frozen else False
                row |= {
                    "speed": 216,
                    "throttle": 104 if bad else 100,
                    "brake": 104 if bad else 0,
                    "n_gear": 8,
                    "rpm": 11000,
                }
            else:
                row |= {"x": 600 * t, "y": 0}  # 1/10 m units
            rows.append(row)
        return rows


def test_constant_speed_lap_has_exact_length():
    lap = load_lap(FakeClient(), 1, 1, T0.isoformat(), 20.0, "fake")
    assert np.isclose(lap.data["Distance"].iloc[-1], 1200.0)
    assert np.isclose(lap.lap_time, 20.0)
    assert lap.data.attrs["gaps_m"] == []


def test_frozen_samples_are_dropped_and_reported():
    lap = load_lap(FakeClient(frozen=(5.0, 6.5)), 1, 1, T0.isoformat(), 20.0, "fake")
    assert lap.data["Throttle"].max() <= 100.0
    ((start, end),) = lap.data.attrs["gaps_m"]
    assert np.isclose(start, 4.75 * 60) and np.isclose(end, 6.75 * 60)
