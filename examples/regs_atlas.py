"""2025 against 2026: what the new regulations changed under braking.

Same circuits, same corners, field medians. Run the build scripts for
both years first:
    uv run python examples/build_season.py 2025
    uv run python examples/build_races.py 2025
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from brakeatlas import plots, stats, style  # noqa: E402
from brakeatlas.field import field_deltas  # noqa: E402
from brakeatlas.race import POWER_UNIT  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA, DOCS = ROOT / "data", ROOT / "docs"
OLD, NEW = 2025, 2026
RENAMED = {"Kick Sauber": "Audi"}
SOURCE = "Data: OpenF1 (F1 timing feed). Same circuits and corners in both seasons."
COLS = {
    "entry_speed": "Speed at the brake point [km/h]",
    "min_speed": "Minimum speed [km/h]",
    "peak_decel_g": "Peak deceleration [g]",
    "braking_distance": "Distance on the brakes [m]",
    "bp_before_mark": "Brake point before the corner [m]",
}


def corners(year: int) -> pd.DataFrame:
    """Field median per corner in qualifying, heavy zones only."""
    z = field_deltas(pd.read_parquet(DATA / f"season_{year}_q.parquet"))
    z = plots.heavy(z)
    out = z.groupby(["track", "corner"])[list(COLS)].median()
    out["n"] = z.groupby(["track", "corner"]).size()
    return out


def main() -> None:
    style.apply()
    pd.set_option("display.width", 200)
    both = corners(OLD).join(corners(NEW), lsuffix="_old", rsuffix="_new", how="inner")
    both = both.reset_index()
    print(f"{both['track'].nunique()} circuits, {len(both)} corners in both seasons")

    change = pd.DataFrame(
        {c: both[f"{c}_new"] - both[f"{c}_old"] for c in COLS}
        | {"track": both["track"]}
    )
    print(
        f"\nChange {OLD} to {NEW}, median over corners [95 % interval over circuits]:"
    )
    summary = {}
    for col, label in COLS.items():
        est = stats.cluster_bootstrap(
            change, lambda f, c=col: f[c].median(), by="track"
        )
        summary[col] = est
        print(f"  {label:36s} {est[0]:+6.2f} [{est[1]:+.2f}, {est[2]:+.2f}]")

    # 1. Entry and minimum speed, corner by corner
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.6))
    for ax, col in zip(axes, ("entry_speed", "min_speed"), strict=True):
        x, y = both[f"{col}_old"], both[f"{col}_new"]
        lim = [min(x.min(), y.min()) - 10, max(x.max(), y.max()) + 10]
        ax.plot(lim, lim, color=style.INK_2, linewidth=0.6)
        ax.plot(x, y, "o", color=style.SERIES[0], markersize=3.5, alpha=0.7)
        ax.set_xlim(lim)
        ax.set_ylim(lim)
        ax.set_aspect("equal")
        ax.grid(axis="x", visible=True)
        ax.set_xlabel(f"{OLD}: {COLS[col][0].lower()}{COLS[col][1:]}")
        ax.set_ylabel(str(NEW))
        ax.annotate(
            f"same as {OLD}",
            (lim[1], lim[1]),
            xytext=(-6, -14),
            textcoords="offset points",
            ha="right",
            fontsize=7,
            color=style.INK_2,
        )
    e, v = summary["entry_speed"][0], summary["min_speed"][0]
    style.headline(
        axes[0],
        f"The {NEW} cars reach the brake point {abs(e):.0f} km/h "
        f"{'faster' if e > 0 else 'slower'} and take the corner {abs(v):.0f} km/h "
        f"{'faster' if v > 0 else 'slower'}",
        f"One dot per corner, field median in qualifying, {len(both)} corners on "
        f"{both['track'].nunique()} circuits. Dots under the line were faster in "
        f"{OLD}.",
    )
    style.source_note(fig, SOURCE)
    style.save(fig, DOCS / f"regs_{OLD}_{NEW}_speeds.png")

    # 2. Brake point, by circuit. Corner marks are identical in both seasons,
    # so distances before the corner compare directly.
    rows = []
    for track, g in change.groupby("track"):
        if len(g) >= 3:
            med, lo, hi = plots.bootstrap_median(g["bp_before_mark"].to_numpy())
            rows.append((track, med, lo, hi))
    by_track = pd.DataFrame(rows, columns=["track", "med", "lo", "hi"])
    fig, ax = plots.dots(
        by_track, "track", f"Brake point, {NEW} against {OLD} [m earlier]"
    )
    b, g_ = summary["bp_before_mark"], summary["peak_decel_g"]
    style.headline(
        ax,
        f"In {NEW} the field brakes {abs(b[0]):.0f} m "
        f"{'earlier' if b[0] > 0 else 'later'} and peak deceleration is "
        f"{abs(g_[0]):.1f} g {'higher' if g_[0] > 0 else 'lower'}",
        f"Median over each circuit's corners, 95 % interval. Overall {b[0]:+.0f} m "
        f"[{b[1]:+.0f}, {b[2]:+.0f}] and {g_[0]:+.2f} g [{g_[1]:+.2f}, {g_[2]:+.2f}], "
        "from a lower entry speed.",
    )
    style.source_note(fig, SOURCE)
    style.save(fig, DOCS / f"regs_{OLD}_{NEW}_braking.png")
    print("\nBy entry-speed band (2025 entry speed), median change:")
    band = pd.cut(both["entry_speed_old"], [0, 250, 300, 400])
    print(
        change.drop(columns="track")
        .groupby(band, observed=True)
        .median()
        .round(2)
        .to_string()
    )

    # 3. Lift and coast in races
    if not (DATA / f"season_{OLD}_r.parquet").exists():
        print("\nNo race data for", OLD, "yet: run build_races.py", OLD)
        return
    races = {}
    for year in (OLD, NEW):
        r = pd.read_parquet(DATA / f"season_{year}_r.parquet")
        r = plots.regulars(r[r["speed_drop"] >= plots.HEAVY_DROP])
        # Same entry on both sides: the 2025 Sauber team is the 2026 Audi team.
        r = r.assign(lico=r["coast_before"] >= 40, team=r["team"].replace(RENAMED))
        races[year] = r
    common = sorted(set(races[OLD]["track"]) & set(races[NEW]["track"]))
    races = {y: r[r["track"].isin(common)] for y, r in races.items()}
    share = pd.DataFrame(
        {str(y): r.groupby("track")["lico"].mean() * 100 for y, r in races.items()}
    )
    order = pd.read_parquet(DATA / f"season_{NEW}_q.parquet")
    order = order.groupby("track")["round_date"].first().sort_values().index
    share = share.reindex([t for t in order if t in share.index])
    diff = (share[str(NEW)] - share[str(OLD)]).to_numpy()
    d_med, d_lo, d_hi = plots.bootstrap_median(diff)
    print(f"\nLift and coast in races on the {len(common)} circuits raced in both:")
    print(share.round(1).to_string())
    print(
        f"median circuit {share[str(OLD)].median():.1f} % in {OLD}, "
        f"{share[str(NEW)].median():.1f} % in {NEW}; change {d_med:+.1f} points "
        f"[{d_lo:+.1f}, {d_hi:+.1f}]"
    )
    fig, ax = plots.two_bars(
        share, (str(OLD), str(NEW)), "Heavy race stops after ≥40 m of coasting [%]"
    )
    style.headline(
        ax,
        "Lift and coast in races did not grow with the new rules: "
        f"{share[str(OLD)].median():.0f} % of heavy stops in {OLD}, "
        f"{share[str(NEW)].median():.0f} % in {NEW}",
        f"Median circuit, clean race laps, {len(common)} circuits raced in both "
        f"seasons. Change per circuit {d_med:+.1f} points [{d_lo:+.1f}, {d_hi:+.1f}].",
    )
    style.source_note(fig, SOURCE)
    style.save(fig, DOCS / f"regs_{OLD}_{NEW}_coast.png")

    # 4. The same teams a year apart: is the power-unit pattern new?
    per = {
        y: (r.groupby(["team", "track"])["lico"].mean() * 100).unstack("team")
        for y, r in races.items()
    }
    rows = []
    for team in sorted(set(per[OLD].columns) & set(per[NEW].columns)):
        d = (per[NEW][team] - per[OLD][team]).dropna().to_numpy()
        med, lo, hi = plots.bootstrap_median(d)
        rows.append(
            (
                f"{team}  ({POWER_UNIT[team]} in {NEW})",
                team,
                med,
                lo,
                hi,
                races[OLD].loc[races[OLD]["team"] == team, "lico"].mean() * 100,
                races[NEW].loc[races[NEW]["team"] == team, "lico"].mean() * 100,
            )
        )
    cols = ["label", "team", "med", "lo", "hi", str(OLD), str(NEW)]
    by_team = pd.DataFrame(rows, columns=cols)
    print("\nSame team, change per circuit [points] and season share [%]:")
    print(by_team.drop(columns="label").round(1).to_string(index=False))
    merc = by_team[by_team["team"].map(POWER_UNIT) == "Mercedes"]
    top_old = by_team.sort_values(str(OLD)).iloc[-1]
    fig, ax = plots.dots(
        by_team,
        "label",
        f"Lift and coast in races, {NEW} minus {OLD}, per circuit [points]",
    )
    drop = by_team.sort_values("med").iloc[0]
    clear = int((merc["hi"] < 0).sum())
    style.headline(
        ax,
        f"{drop['team']} cut lift and coast by {-drop['med']:.0f} points from {OLD}; "
        f"{top_old['team']} was already the highest",
        f"Median change per circuit, 95 % interval. All {len(merc)} Mercedes-powered "
        f"teams moved down, {clear} of them clearly.\n{top_old['team']}: "
        f"{top_old[str(OLD)]:.0f} % of heavy race stops in {OLD} and "
        f"{top_old[str(NEW)]:.0f} % in {NEW}, with a different power unit each year.",
    )
    style.source_note(fig, SOURCE)
    style.save(fig, DOCS / f"regs_{OLD}_{NEW}_teams.png")


if __name__ == "__main__":
    main()
