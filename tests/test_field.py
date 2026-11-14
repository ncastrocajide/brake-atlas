import numpy as np
import pandas as pd
from conftest import G, constant_decel_profile

from brakeatlas.field import lap_zones

V_TOP = 300.0


def stop_length(v_min, decel):
    return ((V_TOP / 3.6) ** 2 - (v_min / 3.6) ** 2) / (2 * decel * G)


def straight_lap(grid, make_lap, corners):
    """Lap along the x axis (X = distance), so marks map onto distance."""
    speed = constant_decel_profile(grid, V_TOP, corners)
    brake = np.zeros(grid.size)
    for bp, v_min, g in corners:
        brake[(grid >= bp) & (grid <= bp + stop_length(v_min, g))] = 100.0
    lap = make_lap(grid, speed, np.where(brake > 0, 0.0, 100.0), brake)
    lap.data["X"] = grid
    lap.data["Y"] = 0.0
    return lap


def marks_at(*positions):
    return pd.DataFrame(
        {
            "Name": [f"T{i + 1}" for i in range(len(positions))],
            "X": positions,
            "Y": 0.0,
        }
    )


def test_zone_takes_first_mark_after_brake_point(grid, make_lap):
    lap = straight_lap(grid, make_lap, [(1000.0, 90.0, 4.0)])
    # A chicane: two marks after the brake point. The zone belongs to the
    # first one, wherever the speed minimum falls.
    frame = lap_zones(lap, marks_at(500.0, 1120.0, 1160.0))
    assert frame["corner"].tolist() == ["T2"]
    assert frame.loc[0, "bp_before_mark"] == 120.0


def test_zone_without_a_mark_in_range_is_dropped(grid, make_lap):
    lap = straight_lap(grid, make_lap, [(1000.0, 90.0, 4.0)])
    assert lap_zones(lap, marks_at(2500.0), max_before=400.0).empty


def test_zone_inside_a_dropout_is_dropped(grid, make_lap):
    lap = straight_lap(grid, make_lap, [(800.0, 90.0, 4.0), (2000.0, 150.0, 3.5)])
    lap.data.attrs["gaps_m"] = [(1990.0, 2040.0)]
    frame = lap_zones(lap, marks_at(900.0, 2100.0))
    assert frame["corner"].tolist() == ["T1"]


def test_tags_are_carried(grid, make_lap):
    lap = straight_lap(grid, make_lap, [(1000.0, 90.0, 4.0)])
    frame = lap_zones(lap, marks_at(1100.0), driver="NOR", session=1)
    assert frame.loc[0, "driver"] == "NOR"


def test_scaled_marks_follow_the_lap_length(grid, make_lap):
    from brakeatlas.field import scaled_marks

    lap = straight_lap(grid, make_lap, [(1000.0, 90.0, 4.0)])  # 3000 m long
    ref = pd.DataFrame({"Name": ["T1"], "Distance": [1090.0]})
    # Reference lap measured the track 1 % shorter: marks move out by 1 %.
    placed = scaled_marks(ref, 3000.0 / 1.01, lap)
    assert np.isclose(placed.loc[0, "Distance"], 1090.0 * 1.01)
    frame = lap_zones(lap, placed, located=True)
    assert frame["corner"].tolist() == ["T1"]
    assert np.isclose(frame.loc[0, "lap_length"], 3000.0)
    assert frame.loc[0, "seg_time"] > 0.0


def test_field_marks_use_the_field_median_not_one_lap():
    from brakeatlas.field import field_marks

    ref = pd.DataFrame({"Name": ["T1", "T2"], "Distance": [1000.0, 2022.0]})
    # Six drivers agree T2 sits at 40 % of the lap; the reference lap,
    # with a dropout before T2, put it 22 m further on.
    zones = pd.DataFrame(
        {"corner": "T2", "mark_distance": 2000.0, "lap_length": 5000.0}, index=range(6)
    )
    placed = field_marks(ref, 5000.0, zones).set_index("Name")["Distance"]
    assert placed["T2"] == 2000.0
    assert placed["T1"] == 1000.0  # no field data: reference value stays
