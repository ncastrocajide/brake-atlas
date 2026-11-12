"""Season-wide braking figures and numbers from the built dataset.

Run examples/build_season.py first. Figures go to docs/, the numbers
behind the README findings are printed.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import pandas as pd  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

from brakeatlas import plots, style  # noqa: E402
from brakeatlas.field import field_deltas  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA, DOCS = ROOT / "data", ROOT / "docs"
DERIVED = ["bp_delta_m", "bp_delta_ms", "bp_z", "vmin_delta", "field_n", "bp_resid_m"]
SOURCE = "Data: OpenF1 (F1 timing feed), fastest qualifying lap per driver."


def main(year: int = 2026) -> None:
    style.apply()
    zones = pd.read_parquet(DATA / f"season_{year}_q.parquet")
    zones = field_deltas(zones.drop(columns=DERIVED, errors="ignore"))
    tracks = pd.read_parquet(DATA / f"tracks_{year}_q.parquet")
    marks = pd.read_parquet(DATA / f"marks_{year}_q.parquet")
    order = list(zones.groupby("track")["round_date"].first().sort_values().index)
    teams = zones.groupby("driver")["team"].agg(lambda s: s.mode()[0]).to_dict()
    heavy = plots.heavy(zones)
    n_tracks = len(order)

    print(
        f"{n_tracks} sessions, {zones['driver'].nunique()} drivers, "
        f"{len(heavy)} heavy zones used, median brake-point uncertainty "
        f"±{heavy['bp_uncertainty_m'].median():.1f} m"
    )

    # 1. Every circuit, braking zones on the map
    fig, axes = plots.track_grid(tracks, marks, zones, order)
    hardest = heavy.groupby(["track", "corner"])["peak_decel_g"].median()
    t_max, c_max = hardest.idxmax()
    style.headline(
        axes.flat[0],
        f"Where the 2026 field brakes: the hardest stop is {c_max} at {t_max} "
        f"({hardest.max():.1f} g)",
        "Coloured stretches run from the median brake point to the corner. "
        "Number after the name: heavy braking zones.",
        pad=14,
    )
    style.source_note(fig, SOURCE + " Corner marks: MultiViewer.")
    style.save(fig, DOCS / f"season_{year}_tracks.png")

    # 2. Drivers by tracks
    fig, ax = plots.season_heatmap(zones, order)
    style.headline(
        ax,
        f"Who brakes late, track by track ({year} qualifying)",
        "Median over each track's heavy braking zones, corrected for entry speed. "
        "Number after the name: season median [m].\nHatched = no clean data.",
        pad=60,
    )
    style.source_note(fig, SOURCE)
    style.save(fig, DOCS / f"season_{year}_heatmap.png")

    # 3. Season index with intervals
    fig, ax, index = plots.driver_index(zones, teams)
    top, bottom = index.iloc[-1], index.iloc[0]
    style.headline(
        ax,
        f"{top['driver']} brakes latest over the season, {bottom['driver']} earliest",
        "Median over all heavy braking zones, corrected for entry speed, with "
        "95 % bootstrap interval.",
    )
    style.source_note(fig, SOURCE)
    style.save(fig, DOCS / f"season_{year}_index.png")

    # 4. Does it pay?
    pace = (
        zones.drop_duplicates(["session", "driver"])
        .assign(
            gap_pct=lambda d: (
                d["gap_to_pole"] / (d["lap_time"] - d["gap_to_pole"]) * 100
            )
        )
        .groupby("driver")["gap_pct"]
        .median()
    )
    fig, ax, joined = plots.pace_scatter(index, pace)
    rho, p = spearmanr(joined["med"], joined["pace"])
    style.headline(
        ax,
        "Braking late and qualifying fast are "
        + ("related" if p < 0.05 else "barely related"),
        f"Spearman rho = {-rho:+.2f} between late braking and pace (p = {p:.2f}, "
        f"{len(joined)} drivers). Grey bars: 95 % interval.",
    )
    style.source_note(fig, SOURCE)
    style.save(fig, DOCS / f"season_{year}_pace.png")

    # Numbers for the write-up
    pd.set_option("display.width", 200)
    print("\nSeason index (m, corrected for entry speed):")
    print(index.assign(team=index["driver"].map(teams)).round(1).to_string(index=False))
    print(f"\nSpearman late braking vs pace: rho={-rho:+.2f} p={p:.3f}")

    mates = index.assign(team=index["driver"].map(teams)).groupby("team")
    print("\nTeammate gaps [m]:")
    for team, g in mates:
        if len(g) == 2:
            g = g.sort_values("med")
            print(
                f"  {team:18s} {g.iloc[1]['driver']} later than "
                f"{g.iloc[0]['driver']} by {g.iloc[1]['med'] - g.iloc[0]['med']:.1f}"
            )

    print("\nTrack braking demand:")
    demand = (
        heavy.groupby("track")
        .agg(
            zones=("corner", "nunique"),
            peak_g=("peak_decel_g", "median"),
            drop_kmh=("speed_drop", "median"),
            spread_m=("bp_resid_m", lambda s: s.quantile(0.75) - s.quantile(0.25)),
        )
        .reindex(order)
    )
    print(demand.round(1).to_string())

    print("\nCoasting before braking, median per team [m] (share of zones > 0):")
    coast = heavy.groupby("team")["coast_before"].agg(
        median="median", share=lambda s: (s > 0).mean()
    )
    print(coast.sort_values("share", ascending=False).round(2).to_string())

    print("\nPeak deceleration vs entry speed (field medians by band):")
    bands = pd.cut(heavy["entry_speed"], [0, 200, 250, 300, 400])
    print(
        heavy.groupby(bands, observed=True)["peak_decel_g"]
        .median()
        .round(2)
        .to_string()
    )


if __name__ == "__main__":
    main()
