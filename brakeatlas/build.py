"""Build the field-wide braking table for one session or a season."""

import pandas as pd
from apextrace.lap import Lap

from brakeatlas.circuits import corner_marks
from brakeatlas.field import field_deltas, lap_zones
from brakeatlas.openf1 import OpenF1, fastest_laps, load_lap, session_laps


def build_session(
    client: OpenF1, session: dict
) -> tuple[pd.DataFrame, Lap, pd.DataFrame]:
    """Braking zones of every driver's fastest lap in a session.

    session: one row of the OpenF1 sessions endpoint.
    Returns (zones with field deltas, the fastest lap of the session
    for track maps, the corner marks).
    """
    key = session["session_key"]
    marks = corner_marks(client, session["circuit_key"], session["year"])
    best = fastest_laps(session_laps(client, key))
    pole_time = best["lap_duration"].min()

    frames, reference = [], None
    for rank, row in enumerate(best.itertuples(), start=1):
        label = f"{row.name_acronym} {session['circuit_short_name']} {session['year']}"
        lap = load_lap(
            client, key, int(row.driver_number), row.date_start, row.lap_duration, label
        )
        if reference is None:
            reference = lap
        frames.append(
            lap_zones(
                lap,
                marks,
                session=key,
                track=session["circuit_short_name"],
                round_date=session["date_start"][:10],
                driver=row.name_acronym,
                team=row.team_name,
                lap_time=row.lap_duration,
                gap_to_pole=row.lap_duration - pole_time,
                rank=rank,
            )
        )
    zones = field_deltas(pd.concat(frames, ignore_index=True))
    return zones, reference, marks
