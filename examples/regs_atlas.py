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

ROOT = Path(__file__).resolve().parents[1]
DATA, DOCS = ROOT / "data", ROOT / "docs"
OLD, NEW = 2025, 2026
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
    share = {}
    teams = {}
    for year in (OLD, NEW):
        r = pd.read_parquet(DATA / f"season_{year}_r.parquet")
        r = plots.regulars(r[r["speed_drop"] >= plots.HEAVY_DROP])
        r = r.assign(lico=r["coast_before"] >= 40)
        share[str(year)] = r.groupby("track")["lico"].mean() * 100
        teams[year] = r.groupby("team")["lico"].mean() * 100
        est = stats.cluster_bootstrap(r, lambda f: f["lico"].mean() * 100, n=300)
        print(
            f"\n{year} races: lift and coast before {est[0]:.1f} % of heavy stops "
            f"[{est[1]:.1f}, {est[2]:.1f}], {r['track'].nunique()} races"
        )
        print(teams[year].sort_values().round(1).to_string())
    coast = pd.DataFrame(share).dropna()
    order = pd.read_parquet(DATA / f"season_{NEW}_q.parquet")
    order = order.groupby("track")["round_date"].first().sort_values().index
    coast = coast.reindex([t for t in order if t in coast.index])
    fig, ax = plots.two_bars(
        coast, (str(OLD), str(NEW)), "Heavy race stops after ≥40 m of coasting [%]"
    )
    ratio = coast[str(NEW)].median() / max(coast[str(OLD)].median(), 0.1)
    style.headline(
        ax,
        f"Lift and coast in races: {coast[str(OLD)].median():.0f} % of heavy stops in "
        f"{OLD}, {coast[str(NEW)].median():.0f} % in {NEW}",
        f"Median circuit, clean race laps, {len(coast)} circuits raced in both "
        f"seasons ({ratio:.1f} times as often).",
    )
    style.source_note(fig, SOURCE)
    style.save(fig, DOCS / f"regs_{OLD}_{NEW}_coast.png")
    print("\nPer circuit:")
    print(coast.round(1).to_string())


if __name__ == "__main__":
    main()
