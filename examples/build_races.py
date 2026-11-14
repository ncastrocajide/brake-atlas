"""Build the braking table for the clean laps of every 2026 race.

Run examples/build_season.py first: it provides the corner marks and
the reference lap length per track. Writes data/season_2026_r.parquet.
The first run downloads one request per driver and race from OpenF1
(about 400 requests, 4-5 MB each before compression).

Usage: uv run python examples/build_races.py [track ...]
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from brakeatlas.field import field_marks
from brakeatlas.openf1 import OpenF1
from brakeatlas.race import build_race

YEAR = 2026
DATA = Path(__file__).resolve().parents[1] / "data"


def main(only: list[str]) -> None:
    client = OpenF1()
    marks = pd.read_parquet(DATA / f"marks_{YEAR}_q.parquet")
    tracks = pd.read_parquet(DATA / f"tracks_{YEAR}_q.parquet")
    quali = pd.read_parquet(DATA / f"season_{YEAR}_q.parquet")
    ref_length = tracks.groupby("track")["Distance"].max()
    now = datetime.now(UTC)
    sessions = [
        s
        for s in client.get("sessions", year=YEAR, session_name="Race")
        if not s.get("is_cancelled")
        and datetime.fromisoformat(s["date_end"]) < now
        and s["circuit_short_name"] in ref_length.index
        and (not only or s["circuit_short_name"] in only)
    ]
    zones, dropped = [], {}
    for s in sessions:
        name = s["circuit_short_name"]
        try:
            length = float(ref_length[name])
            placed = field_marks(
                marks[marks["track"] == name], length, quali[quali["track"] == name]
            )
            z, reasons = build_race(client, s, placed, length)
        except Exception as err:  # one bad race should not stop the season
            print(f"{name:20s} skipped: {err}", flush=True)
            continue
        z["round_date"] = s["date_start"][:10]
        zones.append(z)
        dropped[name] = reasons
        kept = int(reasons.get("ok", 0))
        print(
            f"{name:20s} {kept:4d} of {int(reasons.sum()):4d} laps kept, "
            f"{len(z):5d} zones",
            flush=True,
        )
    suffix = "" if not only else "_" + "_".join(only).lower().replace(" ", "_")
    pd.concat(zones, ignore_index=True).to_parquet(
        DATA / f"season_{YEAR}_r{suffix}.parquet"
    )
    table = pd.DataFrame(dropped).T.fillna(0).astype(int)
    print("\nLaps by filter result:")
    print(table.to_string())
    print(table.sum().to_string())


if __name__ == "__main__":
    main(sys.argv[1:])
