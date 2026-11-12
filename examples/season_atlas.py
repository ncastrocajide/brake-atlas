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
    top2 = {teams[d] for d in index["driver"].iloc[-2:]}
    bottom2 = {teams[d] for d in index["driver"].iloc[:2]}
    title = (
        f"Both {top2.pop()} drivers brake latest, both {bottom2.pop()} drivers earliest"
        if len(top2) == 1 and len(bottom2) == 1
        else f"{index['driver'].iloc[-1]} brakes latest, "
        f"{index['driver'].iloc[0]} earliest"
    )
    style.headline(
        ax,
        title,
        "Median over all heavy braking zones, corrected for entry speed, with "
        "95 % bootstrap interval.",
    )
    style.source_note(fig, SOURCE)
    style.save(fig, DOCS / f"season_{year}_index.png")

    # 4. Pace
    pace = (
        plots.regulars(zones)
        .drop_duplicates(["session", "driver"])
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
        "Faster cars brake later",
        f"Spearman rho = {-rho:+.2f} between late braking and qualifying pace "
        f"({len(joined)} drivers). Teammates sit side by side: the car sets the "
        "brake point more than the driver.",
    )
    style.source_note(fig, SOURCE)
    style.save(fig, DOCS / f"season_{year}_pace.png")

    # 5. Teammates, paired on the same corner and session
    pairs = plots.teammate_pairs(zones)
    fig, ax = plots.teammates(pairs)
    clear = pairs[(pairs["lo"] > 0) | (pairs["hi"] < 0)]
    style.headline(
        ax,
        "Teammates brake within a couple of metres of each other"
        + (
            f", except {', '.join(clear['b'] + ' vs ' + clear['a'])}"
            if len(clear)
            else ""
        ),
        "Median difference over corners both drove in the same session, 95 % "
        "bootstrap interval. Shaded: ±2 m.",
    )
    style.source_note(fig, SOURCE)
    style.save(fig, DOCS / f"season_{year}_teammates.png")

    # 6. Lift and coast through the season
    fig, ax, share = plots.coast_by_round(zones, order)
    first = share.iloc[:3]
    style.headline(
        ax,
        "Lift and coast in qualifying: common in the first rounds, then gone",
        f"{first.max():.0f} % of heavy stops at {first.idxmax()} followed 40 m or more "
        "of coasting, under 3 % from Miami on. Shorter coasts are below what 4 Hz data "
        "can resolve.",
    )
    style.source_note(fig, SOURCE)
    style.save(fig, DOCS / f"season_{year}_coast.png")

    # Numbers for the write-up
    pd.set_option("display.width", 200)
    print("\nSeason index (m, corrected for entry speed):")
    print(index.assign(team=index["driver"].map(teams)).round(1).to_string(index=False))
    print(f"\nSpearman late braking vs pace: rho={-rho:+.2f} p={p:.3f}")

    print("\nTeammates, paired [m]:")
    print(pairs.round(1).to_string(index=False))
    drivers = heavy.groupby(["team", "driver"])[plots.METRIC].median().reset_index()
    drivers = drivers[drivers["driver"].isin(index["driver"])]
    team_mean = drivers.groupby("team")[plots.METRIC].transform("mean")
    within = ((drivers[plots.METRIC] - team_mean) ** 2).sum() / (
        len(drivers) - drivers["team"].nunique()
    )
    print(
        f"Variance of driver medians: between teams {team_mean.var():.1f}, "
        f"within teams {within:.1f} m^2"
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

    print("\nLift and coast >= 40 m before a heavy stop, share of zones:")
    coast = heavy.assign(coast=heavy["coast_before"] >= 40.0)
    print(
        coast.groupby("team")["coast"]
        .mean()
        .sort_values(ascending=False)
        .round(3)
        .to_string()
    )
    print(
        coast.groupby("track")["coast"]
        .mean()
        .sort_values(ascending=False)
        .head(6)
        .round(3)
        .to_string()
    )
    print(f"overall {coast['coast'].mean():.3f}")

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
