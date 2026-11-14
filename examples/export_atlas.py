"""Export the data behind docs/index.html (the interactive atlas).

Writes docs/atlas_data.js: track outlines, braking zones and, per corner,
each driver's qualifying numbers and race-vs-qualifying margin.
Run the build and atlas scripts first.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from race_atlas import scaled_quali

from brakeatlas import plots, stats
from brakeatlas.field import field_deltas

ROOT = Path(__file__).resolve().parents[1]
DATA, DOCS = ROOT / "data", ROOT / "docs"
YEAR = 2026
SIZE = 1000.0  # every track is scaled into a SIZE x SIZE box


def main() -> None:
    zones = field_deltas(pd.read_parquet(DATA / f"season_{YEAR}_q.parquet"))
    tracks = pd.read_parquet(DATA / f"tracks_{YEAR}_q.parquet")
    marks = pd.read_parquet(DATA / f"marks_{YEAR}_q.parquet")
    heavy = plots.heavy(zones)

    margin = {}
    race_file = DATA / f"season_{YEAR}_r.parquet"
    if race_file.exists():
        race = pd.read_parquet(race_file)
        race = race[race["speed_drop"] >= plots.HEAVY_DROP]
        m = stats.race_margin(scaled_quali(heavy, marks, tracks), race)
        margin = m.set_index(["track", "driver", "corner"])["margin_m"].to_dict()

    out = []
    order = heavy.groupby("track")["round_date"].first().sort_values().index
    for name in order:
        t = tracks[tracks["track"] == name]
        x, y, d = (t[c].to_numpy(dtype=float) for c in ("X", "Y", "Distance"))
        span = max(np.ptp(x), np.ptp(y))
        # Same scale on both axes, centred, y flipped for screen coordinates.
        mid_x, mid_y = (x.min() + x.max()) / 2, (y.min() + y.max()) / 2
        px = (x - mid_x) / span * SIZE * 0.86 + SIZE / 2
        py = -(y - mid_y) / span * SIZE * 0.86 + SIZE / 2
        points = np.column_stack([px, py]).round(1)

        corners = []
        z = heavy[heavy["track"] == name]
        located = marks[marks["track"] == name].set_index("Name")["Distance"]
        for corner, g in z.groupby("corner"):
            at = float(located[corner])
            i_mark = int(np.argmin(np.abs(d - at)))
            sel = (d >= at - g["bp_before_mark"].median()) & (d <= at)
            drivers = [
                {
                    "d": r.driver,
                    "team": r.team,
                    "late": round(r.bp_resid_m, 1) if pd.notna(r.bp_resid_m) else None,
                    "bp": round(r.bp_before_mark),
                    "entry": round(r.entry_speed),
                    "vmin": round(r.min_speed),
                    "peak": round(r.peak_decel_g, 2),
                    "race": (
                        round(margin[(name, r.driver, corner)], 1)
                        if (name, r.driver, corner) in margin
                        else None
                    ),
                }
                for r in g.sort_values("rank").itertuples()
            ]
            corners.append(
                {
                    "name": corner,
                    "at": round(at),
                    "x": points[i_mark, 0],
                    "y": points[i_mark, 1],
                    "seg": points[sel].tolist(),
                    "bp": round(g["bp_before_mark"].median()),
                    "entry": round(g["entry_speed"].median()),
                    "vmin": round(g["min_speed"].median()),
                    "peak": round(g["peak_decel_g"].median(), 2),
                    "drivers": drivers,
                }
            )
        corners.sort(key=lambda c: c["at"])
        out.append(
            {
                "name": name,
                "date": z["round_date"].iloc[0],
                "outline": points[::3].tolist(),
                "order": (
                    z.sort_values("rank").drop_duplicates("driver")["driver"].tolist()
                ),
                "corners": corners,
            }
        )
    text = "window.ATLAS = " + json.dumps({"year": YEAR, "tracks": out}) + ";\n"
    (DOCS / "atlas_data.js").write_text(text)
    print(f"{len(out)} tracks, {len(text) / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
