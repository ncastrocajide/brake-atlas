"""Build the braking table for every 2026 qualifying session run so far.

Writes data/season_2026_q.parquet (one row per braking zone) and
data/tracks_2026_q.parquet (the fastest lap of each session, for maps).
The first run downloads from OpenF1 into .openf1_cache/ (about a
thousand small requests); later runs read from the cache.
"""

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from apextrace.corners import locate_marks

from brakeatlas.build import build_session
from brakeatlas.openf1 import OpenF1

YEAR = 2026
OUT = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    client = OpenF1()
    now = datetime.now(UTC)
    sessions = [
        s
        for s in client.get("sessions", year=YEAR, session_name="Qualifying")
        if not s.get("is_cancelled") and datetime.fromisoformat(s["date_end"]) < now
    ]
    zones, tracks, marks_all = [], [], []
    for s in sessions:
        name = s["circuit_short_name"]
        try:
            z, ref, marks = build_session(client, s)
        except Exception as err:  # one bad session should not stop the season
            print(f"{name:20s} skipped: {err}")
            continue
        zones.append(z)
        t = ref.data[["Distance", "X", "Y", "Speed"]].copy()
        t["track"] = name
        tracks.append(t)
        m = locate_marks(ref, marks)
        m["track"] = name
        marks_all.append(m)
        per_corner = z.groupby("corner").size()
        print(
            f"{name:20s} {z['driver'].nunique():2d} drivers, {len(z):3d} zones, "
            f"{per_corner.size:2d} corners, median coverage {per_corner.median():.0f}"
        )
    OUT.mkdir(exist_ok=True)
    pd.concat(zones, ignore_index=True).to_parquet(OUT / f"season_{YEAR}_q.parquet")
    pd.concat(tracks, ignore_index=True).to_parquet(OUT / f"tracks_{YEAR}_q.parquet")
    pd.concat(marks_all, ignore_index=True).to_parquet(OUT / f"marks_{YEAR}_q.parquet")


if __name__ == "__main__":
    main()
