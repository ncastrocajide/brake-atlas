import pandas as pd

from brakeatlas.race import clean_laps


def race(n_laps=12):
    laps = pd.DataFrame(
        {
            "driver_number": 1,
            "lap_number": range(1, n_laps + 1),
            "lap_duration": 90.0,
            "is_pit_out_lap": False,
        }
    )
    stints = pd.DataFrame(
        {
            "driver_number": [1, 1],
            "stint_number": [1, 2],
            "lap_start": [1, 7],
            "lap_end": [6, n_laps],
            "compound": ["MEDIUM", "HARD"],
            "tyre_age_at_start": [0, 3],
        }
    )
    pits = pd.DataFrame({"driver_number": [1], "lap_number": [6]})
    control = pd.DataFrame(
        {
            "lap_number": [9, 4],
            "flag": ["YELLOW", "BLUE"],
            "category": ["Flag", "Flag"],
        }
    )
    laps.loc[laps["lap_number"] == 7, "is_pit_out_lap"] = True
    laps.loc[laps["lap_number"] == 11, "lap_duration"] = 120.0
    laps.loc[laps["lap_number"] == 3, "lap_duration"] = None
    return laps, stints, pits, control


def test_each_filter_names_its_reason():
    tagged = clean_laps(*race()).set_index("lap_number")
    reasons = tagged["reason"].to_dict()
    assert reasons[1] == "lap1"
    assert reasons[3] == "no_time"
    assert reasons[6] == "pit_in"
    assert reasons[7] == "pit_out"
    assert reasons[9] == "flag"
    assert reasons[11] == "slow"
    # Blue flags are for lapped cars, not a reason to drop the lap.
    assert [n for n, r in reasons.items() if r == "ok"] == [2, 4, 5, 8, 10, 12]


def test_stint_and_tyre_age_are_attached():
    tagged = clean_laps(*race()).set_index("lap_number")
    assert tagged.loc[5, ["stint", "compound", "tyre_age"]].tolist() == [1, "MEDIUM", 4]
    # Second stint started on tyres that already had 3 laps.
    assert tagged.loc[8, ["stint", "compound", "tyre_age"]].tolist() == [2, "HARD", 4]


def test_wet_stint_is_dropped():
    laps, stints, pits, control = race()
    stints.loc[1, "compound"] = "INTERMEDIATE"
    tagged = clean_laps(laps, stints, pits, control).set_index("lap_number")
    assert tagged.loc[8, "reason"] == "not_dry"
