"""Track map and driver-by-corner heatmap for one qualifying session.

Usage: uv run python examples/session_atlas.py Monza
Figures go to docs/.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from apextrace.corners import locate_marks  # noqa: E402

from brakeatlas import plots, style  # noqa: E402
from brakeatlas.build import build_session  # noqa: E402
from brakeatlas.openf1 import OpenF1  # noqa: E402

DOCS = Path(__file__).resolve().parents[1] / "docs"


def main(track: str, year: int = 2026) -> None:
    style.apply()
    client = OpenF1()
    session = next(
        s
        for s in client.get("sessions", year=year, session_name="Qualifying")
        if s["circuit_short_name"] == track
    )
    zones, ref, marks = build_session(client, session)
    slug = track.lower().replace(" ", "_")
    heavy = plots.heavy(zones, min_field=8)
    unc = zones["bp_uncertainty_m"].median()

    # Track map
    fig, ax = plt.subplots(figsize=(7, 6))
    lines = plots.track_map(ax, ref.data, locate_marks(ref, marks), heavy)
    cb = fig.colorbar(lines, ax=ax, shrink=0.5, pad=0.01)
    cb.outline.set_visible(False)
    cb.set_label("Field median peak deceleration [g]")
    top = heavy.groupby("corner")["peak_decel_g"].median().idxmax()
    style.headline(
        ax,
        f"{track} {year}: the hardest stop is {top}",
        "Coloured stretch: from where the field's median driver brakes to the "
        "corner. Fastest qualifying laps.",
    )
    style.source_note(fig, "Data: OpenF1 (F1 timing feed). Corner marks: MultiViewer.")
    style.save(fig, DOCS / f"{slug}_{year}_q_map.png")

    # Heatmap
    fig, ax = plots.session_heatmap(zones)
    style.headline(
        ax,
        f"{track} {year} qualifying: brake points against the field",
        "Red = brakes later than expected for the speed it arrives at.\n"
        f"One brake point is known to about ±{unc:.0f} m (4 Hz data), so single "
        "cells are noisy. Hatched = no clean data.",
        pad=16,
    )
    style.source_note(
        fig, "Data: OpenF1 (F1 timing feed). Drivers in qualifying order."
    )
    style.save(fig, DOCS / f"{slug}_{year}_q_heatmap.png")
    print(
        heavy.groupby("corner")[["bp_before_mark", "peak_decel_g", "bp_uncertainty_m"]]
        .median()
        .round(1)
    )


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "Monza")
