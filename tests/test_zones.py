import numpy as np
import pytest
from conftest import STEP, G, constant_decel_profile

from brakeatlas.zones import detect_brake_zones, zones_to_frame

V_TOP, V_MIN, DECEL = 300.0, 100.0, 4.0
BRAKE_AT, COAST = 1000.0, 50.0
# Closed-form stopping distance of a constant-g stop.
D_STOP = ((V_TOP / 3.6) ** 2 - (V_MIN / 3.6) ** 2) / (2 * DECEL * G)


def single_stop(grid, make_lap, coast=COAST, gap=None):
    speed = constant_decel_profile(grid, V_TOP, [(BRAKE_AT, V_MIN, DECEL)])
    braking = (grid >= BRAKE_AT) & (grid <= BRAKE_AT + D_STOP)
    brake = np.where(braking, 100.0, 0.0)
    if gap is not None:  # brake signal drops out over [gap[0], gap[1])
        brake[(grid >= gap[0]) & (grid < gap[1])] = 0.0
    throttle = np.where(
        (grid >= BRAKE_AT - coast) & (grid <= BRAKE_AT + D_STOP), 0, 100.0
    )
    return make_lap(grid, speed, throttle, brake)


def test_single_stop_matches_closed_form(grid, make_lap):
    zones = detect_brake_zones(single_stop(grid, make_lap))
    assert len(zones) == 1
    z = zones[0]
    assert z.brake_point == BRAKE_AT
    assert z.entry_speed == pytest.approx(V_TOP)
    assert z.min_speed == pytest.approx(V_MIN, abs=1.0)
    assert z.braking_distance == pytest.approx(D_STOP, abs=STEP)
    assert z.mean_decel_g == pytest.approx(DECEL, rel=0.05)
    assert z.peak_decel_g == pytest.approx(DECEL, rel=0.05)
    assert z.coast_before == pytest.approx(COAST, abs=STEP)
    assert abs(z.release_offset) <= STEP


def test_no_coast_when_braking_straight_off_throttle(grid, make_lap):
    z = detect_brake_zones(single_stop(grid, make_lap, coast=0.0))[0]
    assert z.coast_before == 0.0


def test_brake_flicker_is_one_zone(grid, make_lap):
    lap = single_stop(grid, make_lap, gap=(BRAKE_AT + 30.0, BRAKE_AT + 40.0))
    zones = detect_brake_zones(lap, merge_gap=20.0)
    assert len(zones) == 1
    assert zones[0].brake_point == BRAKE_AT


def test_dab_without_speed_loss_is_discarded(grid, make_lap):
    speed = np.full(grid.size, V_TOP)
    brake = np.where((grid >= 500.0) & (grid < 520.0), 100.0, 0.0)
    lap = make_lap(grid, speed, np.full(grid.size, 100.0), brake)
    assert detect_brake_zones(lap) == []


def test_two_corners_in_track_order(grid, make_lap):
    corners = [(800.0, 90.0, 4.5), (2000.0, 150.0, 3.5)]
    speed = constant_decel_profile(grid, V_TOP, corners)
    brake = np.zeros(grid.size)
    for bp, v_min, g in corners:
        d = ((V_TOP / 3.6) ** 2 - (v_min / 3.6) ** 2) / (2 * g * G)
        brake[(grid >= bp) & (grid <= bp + d)] = 100.0
    lap = make_lap(grid, speed, np.where(brake > 0, 0.0, 100.0), brake)

    zones = detect_brake_zones(lap)
    assert [z.number for z in zones] == [1, 2]
    assert [z.brake_point for z in zones] == [800.0, 2000.0]
    assert zones[0].min_speed == pytest.approx(90.0, abs=1.0)
    assert zones[1].min_speed == pytest.approx(150.0, abs=1.0)
    # The harder stop must read as the higher deceleration.
    assert zones[0].mean_decel_g > zones[1].mean_decel_g


def test_frame_carries_tags(grid, make_lap):
    zones = detect_brake_zones(single_stop(grid, make_lap))
    frame = zones_to_frame(zones, driver="NOR", track="Monza")
    assert list(frame.columns[:2]) == ["track", "driver"]
    assert len(frame) == 1
    assert frame.loc[0, "brake_point"] == BRAKE_AT


def test_entry_speed_correction_removes_slow_car_advantage():
    import pandas as pd

    from brakeatlas.field import field_deltas

    # Ten drivers whose brake point follows v^2 exactly: no one is late
    # once entry speed is accounted for, even though slow cars brake
    # closer to the corner.
    v = np.linspace(290.0, 330.0, 10)
    frame = pd.DataFrame(
        {
            "session": 1,
            "corner": "T1",
            "entry_speed": v,
            "bp_before_mark": 20.0 + 0.012 * (v / 3.6) ** 2,
            "min_speed": 80.0,
        }
    )
    out = field_deltas(frame)
    assert out["bp_delta_m"].abs().max() > 5.0  # raw delta sees a spread
    assert out["bp_resid_m"].abs().max() < 1e-6  # corrected delta does not
