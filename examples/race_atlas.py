"""Race figures and numbers: qualifying against race, lap-to-lap scatter,
tyre and fuel drift, lift and coast.

Run examples/build_season.py and examples/build_races.py first.
Usage: uv run python examples/race_atlas.py [race-parquet-suffix]
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from brakeatlas import plots, stats, style  # noqa: E402
from brakeatlas.field import field_marks  # noqa: E402
from brakeatlas.race import POWER_UNIT  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA, DOCS = ROOT / "data", ROOT / "docs"
SOURCE = (
    "Data: OpenF1 (F1 timing feed). Clean race laps: green flag, dry tyres, "
    "no pit laps."
)
YEAR = 2026


def scaled_quali(quali, marks, tracks):
    """Qualifying brake points measured like the race ones (scaled marks)."""
    out = []
    ref_length = tracks.groupby("track")["Distance"].max()
    for name, q in quali.groupby("track"):
        placed = field_marks(marks[marks["track"] == name], ref_length[name], q)
        at = q["corner"].map(placed.set_index("Name")["Distance"])
        out.append(
            q.assign(
                bp_scaled=at * q["lap_length"] / ref_length[name] - q["brake_point"]
            )
        )
    return pd.concat(out)


def main(suffix: str = "") -> None:
    style.apply()
    pd.set_option("display.width", 200)
    race = pd.read_parquet(DATA / f"season_{YEAR}_r{suffix}.parquet")
    quali = pd.read_parquet(DATA / f"season_{YEAR}_q.parquet")
    quali = quali[quali["track"].isin(race["track"].unique())]
    quali = scaled_quali(
        quali,
        pd.read_parquet(DATA / f"marks_{YEAR}_q.parquet"),
        pd.read_parquet(DATA / f"tracks_{YEAR}_q.parquet"),
    )
    order = list(race.groupby("track")["round_date"].first().sort_values().index)
    heavy = race[race["speed_drop"] >= plots.HEAVY_DROP]
    heavy = plots.regulars(heavy)
    laps = race.groupby(["session", "driver", "lap_number"]).ngroups
    print(f"{len(order)} races, {laps} clean laps, {len(heavy)} heavy zones")

    # 1. Qualifying against race
    m = stats.race_margin(quali[quali["speed_drop"] >= plots.HEAVY_DROP], heavy)
    med = lambda col: lambda f: f[col].median()  # noqa: E731
    all_m, lo, hi = stats.cluster_bootstrap(m, med("margin_m"), by="track")
    print(
        f"\nRace vs qualifying over {len(m)} driver-corners: brake point "
        f"{all_m:+.1f} m earlier [{lo:+.1f}, {hi:+.1f}], entry speed "
        f"{m['entry_delta'].median():+.1f} km/h, min speed "
        f"{m['vmin_delta'].median():+.1f} km/h, peak decel "
        f"{m['peak_delta'].median():+.2f} g"
    )
    rows = []
    for team, g in m.groupby("team"):
        rows.append((team, *stats.cluster_bootstrap(g, med("margin_m"), by="track")))
    by_team = pd.DataFrame(rows, columns=["team", "med", "lo", "hi"])
    print(by_team.sort_values("med").round(1).to_string(index=False))
    fig, ax = plots.dots(
        by_team, "team", "Brake point in the race against qualifying [m earlier]"
    )
    style.headline(
        ax,
        f"On Sunday the field brakes {all_m:.0f} m earlier than in qualifying",
        f"Median over {len(m)} driver-corner pairs, same driver and corner, 95 % "
        f"interval over races.\nEntry speed is {-m['entry_delta'].median():.0f} km/h "
        "lower in the race, which alone would allow braking later.",
    )
    style.source_note(fig, SOURCE)
    style.save(fig, DOCS / f"race_{YEAR}_margin.png")

    # 2. Lap-to-lap scatter
    pairs = stats.lap_pairs(heavy)
    field_s = stats.spread(pairs)
    rows = []
    for driver, g in pairs.groupby("driver"):
        if g["session"].nunique() >= min(5, len(order)):
            rows.append(
                (
                    f"{driver}  ({g['team'].mode()[0]})",
                    driver,
                    *stats.cluster_bootstrap(g, stats.spread),
                    len(g),
                )
            )
    by_driver = pd.DataFrame(rows, columns=["label", "driver", "med", "lo", "hi", "n"])
    print(
        f"\nLap-to-lap brake-point scatter, field: {field_s:.1f} m "
        f"({len(pairs)} consecutive-lap pairs; raw sd of differences "
        f"{pairs['d'].std():.1f} m, sampling part "
        f"{np.sqrt(pairs['noise'].mean()):.1f} m)"
    )
    print(
        by_driver.drop(columns="label")
        .sort_values("med")
        .round(1)
        .to_string(index=False)
    )
    best, worst = by_driver.sort_values("med").iloc[[0, -1]]["driver"]
    fig, ax = plots.dots(
        by_driver,
        "label",
        "Lap-to-lap scatter of the brake point, sampling noise removed [m]",
    )
    style.headline(
        ax,
        f"The brake point moves about {field_s:.0f} m from lap to lap for everyone; "
        f"only the ends ({best}, {worst}) differ",
        "Standard deviation between consecutive clean laps of a stint, same corner, "
        "95 % interval over races.\nIt is not only the driver: traffic and energy "
        "management move a race brake point too.",
    )
    style.source_note(fig, SOURCE)
    style.save(fig, DOCS / f"race_{YEAR}_scatter.png")

    # 3. Tyres and fuel
    print("\nDrift per 10 laps [tyre age, race distance], 95 % interval over races:")
    for col, unit in (
        ("bp_before_mark", "m earlier"),
        ("entry_speed", "km/h"),
        ("min_speed", "km/h"),
        ("peak_decel_g", "g"),
    ):
        est, lo, hi = stats.cluster_bootstrap(
            heavy, lambda f, c=col: stats.stint_slopes(f, c) * 10.0
        )
        print(
            f"  {col:15s} tyres {est[0]:+.2f} [{lo[0]:+.2f}, {hi[0]:+.2f}]   "
            f"fuel {est[1]:+.2f} [{lo[1]:+.2f}, {hi[1]:+.2f}]  {unit}"
        )
    slope, lo_s, hi_s = stats.cluster_bootstrap(
        heavy, lambda f: stats.stint_slopes(f) * 10.0
    )
    keys = ["session", "driver", "stint", "corner"]
    h = heavy[heavy.groupby(keys)["lap_number"].transform("size") >= 8]
    rel = h["bp_before_mark"] - h.groupby(keys)["bp_before_mark"].transform("mean")
    age = h["tyre_age"] - h.groupby(keys)["tyre_age"].transform("mean")
    bins = pd.cut(age, np.arange(-14, 15, 4))
    g = rel.groupby(bins, observed=True)
    x = np.array([b.mid for b in g.mean().index])
    se = g.std() / np.sqrt(g.size())
    fig, ax = plots.trend(
        x,
        g.mean(),
        g.mean() - 1.96 * se,
        g.mean() + 1.96 * se,
        "Laps relative to the middle of the stint",
        "Brake point vs stint average [m earlier]",
    )
    style.headline(
        ax,
        "Within a stint the brake point moves "
        + ("earlier" if g.mean().iloc[-1] > g.mean().iloc[0] else "later"),
        f"Model over all races: {slope[0]:+.1f} m per 10 laps of tyre age "
        f"[{lo_s[0]:+.1f}, {hi_s[0]:+.1f}], {slope[1]:+.1f} m per 10 laps of race "
        f"distance [{lo_s[1]:+.1f}, {hi_s[1]:+.1f}] (positive = earlier).",
    )
    style.source_note(fig, SOURCE)
    style.save(fig, DOCS / f"race_{YEAR}_stint.png")

    # 4. Lift and coast, race against qualifying
    qh = quali[quali["speed_drop"] >= plots.HEAVY_DROP]
    coast = pd.DataFrame(
        {
            "quali": (qh["coast_before"] >= 40).groupby(qh["track"]).mean() * 100,
            "race": (heavy["coast_before"] >= 40).groupby(heavy["track"]).mean() * 100,
        }
    ).reindex(order)
    print("\nLift and coast >= 40 m, % of heavy stops:")
    print(coast.round(1).to_string())
    team_coast = (heavy["coast_before"] >= 40).groupby(heavy["team"]).mean() * 100
    print(team_coast.sort_values().round(1).to_string())
    fig, ax = plots.two_bars(
        coast, ("qualifying", "race"), "Heavy stops after ≥40 m of coasting [%]"
    )
    style.headline(
        ax,
        f"Lift and coast is a race tool: {coast['race'].median():.0f} % of heavy "
        f"stops on Sunday, {coast['quali'].median():.0f} % on Saturday",
        "Median round. Coasting 40 m or more off throttle before the brake point. "
        f"By team in races: {team_coast.min():.0f} % ({team_coast.idxmin()}) to "
        f"{team_coast.max():.0f} % ({team_coast.idxmax()}).",
    )
    style.source_note(fig, SOURCE)
    style.save(fig, DOCS / f"race_{YEAR}_coast.png")

    # 5. Lift and coast by power unit
    by_pu = heavy.assign(
        pu=heavy["team"].map(POWER_UNIT), lico=heavy["coast_before"] >= 40
    )
    rows = []
    for pu, g in by_pu.groupby("pu"):
        est = stats.cluster_bootstrap(g, lambda f: f["lico"].mean() * 100, n=300)
        teams = g["team"].nunique()
        rows.append((f"{pu}  ({teams} team{'s' if teams > 1 else ''})", pu, *est))
    pu_table = pd.DataFrame(rows, columns=["label", "pu", "med", "lo", "hi"])
    per_race = (by_pu.groupby(["track", "pu"])["lico"].mean()).unstack()
    top, low = pu_table.sort_values("med").iloc[[-1, 0]].itertuples()
    wins = int((per_race.idxmax(axis=1) == top.pu).sum())
    print("\nLift and coast by power unit, % of heavy race stops:")
    print(pu_table.drop(columns="label").round(1).to_string(index=False))
    print(f"{top.pu} highest in {wins} of {len(per_race)} races")
    fig, ax = plots.dots(
        pu_table, "label", "Heavy race stops after ≥40 m of coasting [%]"
    )
    style.headline(
        ax,
        f"{top.pu} cars lift and coast {top.med / low.med:.1f} times as often as "
        f"{low.pu} cars",
        f"{top.med:.0f} % against {low.med:.0f} % of heavy stops in clean race laps, "
        f"95 % interval over races. {top.pu} is the highest in {wins} of "
        f"{len(per_race)} races.\nTeams sharing a power unit sit together, which "
        "points at energy management more than at driving style.",
    )
    style.source_note(fig, SOURCE)
    style.save(fig, DOCS / f"race_{YEAR}_power_unit.png")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
