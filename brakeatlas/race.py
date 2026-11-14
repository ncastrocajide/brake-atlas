"""Race laps: pick the clean ones and extract their braking zones.

A race lap is only comparable if the driver was simply driving: no pit
stop, no flags, dry tyres, normal pace. Everything else is filtered out
and counted, so the build log shows what was dropped and why.
"""

from datetime import timedelta

import numpy as np
import pandas as pd

from brakeatlas.field import lap_zones, scaled_marks
from brakeatlas.openf1 import OpenF1, _when, build_lap, car_samples

DRY = {"SOFT", "MEDIUM", "HARD"}

# 2026 power-unit supply, by team name as OpenF1 writes it.
POWER_UNIT = {
    "Mercedes": "Mercedes",
    "McLaren": "Mercedes",
    "Williams": "Mercedes",
    "Alpine": "Mercedes",
    "Ferrari": "Ferrari",
    "Haas F1 Team": "Ferrari",
    "Cadillac": "Ferrari",
    "Red Bull Racing": "Red Bull Ford",
    "Racing Bulls": "Red Bull Ford",
    "Aston Martin": "Honda",
    "Audi": "Audi",
}
FLAGS = {"YELLOW", "DOUBLE YELLOW", "RED"}


def clean_laps(
    laps: pd.DataFrame,
    stints: pd.DataFrame,
    pits: pd.DataFrame,
    race_control: pd.DataFrame,
    slow: float = 1.05,
) -> pd.DataFrame:
    """Tag every race lap with its stint and the reason it is not clean.

    Adds stint, compound, tyre_age and reason. reason is "ok" or the
    first of: no_time, lap1, pit_out, pit_in, no_stint, not_dry, flag
    (a yellow, red or safety-car message on that lap number), slow
    (more than `slow` times the driver's median over the laps of that
    stint still standing, which catches safety-car and damaged laps).
    """
    out = laps.copy()
    out["stint"] = -1
    out["compound"] = None
    out["tyre_age"] = -1
    for s in stints.itertuples():
        hit = (
            (out["driver_number"] == s.driver_number)
            & (out["lap_number"] >= s.lap_start)
            & (out["lap_number"] <= s.lap_end)
        )
        out.loc[hit, "stint"] = s.stint_number
        out.loc[hit, "compound"] = s.compound
        out.loc[hit, "tyre_age"] = (
            s.tyre_age_at_start + out.loc[hit, "lap_number"] - s.lap_start
        )

    pit_in = set(zip(pits["driver_number"], pits["lap_number"], strict=True))
    flagged = set(
        race_control.loc[
            race_control["flag"].isin(FLAGS)
            | (race_control["category"] == "SafetyCar"),
            "lap_number",
        ].dropna()
    )

    def reason(row) -> str:
        if pd.isna(row["lap_duration"]):
            return "no_time"
        if row["lap_number"] == 1:
            return "lap1"
        if row["is_pit_out_lap"]:
            return "pit_out"
        if (row["driver_number"], row["lap_number"]) in pit_in:
            return "pit_in"
        if row["stint"] < 0:
            return "no_stint"
        if row["compound"] not in DRY:
            return "not_dry"
        if row["lap_number"] in flagged:
            return "flag"
        return "ok"

    out["reason"] = out.apply(reason, axis=1)
    ok = out["reason"] == "ok"
    median = (
        out[ok].groupby(["driver_number", "stint"])["lap_duration"].transform("median")
    )
    too_slow = out.loc[ok, "lap_duration"] > slow * median
    out.loc[too_slow[too_slow].index, "reason"] = "slow"
    return out


def build_race(
    client: OpenF1,
    session: dict,
    marks: pd.DataFrame,
    ref_length: float,
    length_tol: float = 0.01,
) -> tuple[pd.DataFrame, pd.Series]:
    """Braking zones of every clean lap of a race.

    marks: corner marks located on a reference lap (Name, Distance);
    ref_length: that lap's length. Race laps are fetched without
    position data, so marks are scaled onto each lap by lap length.
    Laps whose integrated length is more than length_tol away from the
    race's median lap are dropped (reason "length"): their telemetry
    has holes.

    Returns (zones, count of laps per reason).
    """
    key = session["session_key"]
    laps = pd.DataFrame(client.get("laps", session_key=key))
    drivers = pd.DataFrame(client.get("drivers", session_key=key))
    drivers = drivers.drop_duplicates("driver_number").set_index("driver_number")
    tagged = clean_laps(
        laps,
        pd.DataFrame(client.get("stints", session_key=key)),
        pd.DataFrame(client.get("pit", session_key=key)),
        pd.DataFrame(client.get("race_control", session_key=key)),
    )

    built = []
    for number, own in tagged.groupby("driver_number"):
        good = own[own["reason"] == "ok"]
        if good.empty or number not in drivers.index:
            continue
        starts = good["date_start"].map(_when)
        car = car_samples(
            client,
            key,
            int(number),
            starts.min() - timedelta(seconds=5),
            starts.max() + timedelta(seconds=float(good["lap_duration"].max()) + 5),
        )
        if car.empty:
            tagged.loc[good.index, "reason"] = "no_data"
            continue
        who = drivers.loc[number]
        for row in good.itertuples():
            try:
                lap = build_lap(
                    car,
                    _when(row.date_start).timestamp(),
                    row.lap_duration,
                    f"{who['name_acronym']} lap {row.lap_number}",
                )
            except ValueError:
                tagged.loc[row.Index, "reason"] = "no_data"
                continue
            built.append(
                (
                    row.Index,
                    float(lap.data["Distance"].iloc[-1]),
                    lap_zones(
                        lap,
                        scaled_marks(marks, ref_length, lap),
                        located=True,
                        session=key,
                        track=session["circuit_short_name"],
                        driver=who["name_acronym"],
                        team=who["team_name"],
                        lap_number=row.lap_number,
                        lap_time=row.lap_duration,
                        stint=row.stint,
                        compound=row.compound,
                        tyre_age=row.tyre_age,
                    ),
                )
            )

    # The yardstick is the race's own median lap, not the qualifying
    # reference: the two can differ by more than the tolerance (Suzuka
    # and the Hungaroring lost nearly every lap that way).
    typical = float(np.median([length for _, length, _ in built])) if built else 0.0
    frames = []
    for index, length, frame in built:
        if abs(length / typical - 1.0) > length_tol:
            tagged.loc[index, "reason"] = "length"
        else:
            frames.append(frame)
    zones = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return zones, tagged["reason"].value_counts()
