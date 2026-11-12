"""Figures for the braking atlas. All use brakeatlas.style.

Every function returns the figure; callers add a headline and save.
Zones passed in are expected to carry field deltas (field_deltas).
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection

from brakeatlas import style

HEAVY_DROP = 50.0  # km/h: below this a "braking zone" is a lift or a dab
METRIC = "bp_resid_m"  # brake-point delta corrected for entry speed
LABEL = "Brakes later than expected for its entry speed [m]"


MIN_ZONES = 30  # per driver, for season numbers: leaves out one-off substitutes


def heavy(zones: pd.DataFrame, min_field: int = 10) -> pd.DataFrame:
    """Zones that are real stops, at corners most of the field has data for."""
    return zones[(zones["speed_drop"] >= HEAVY_DROP) & (zones["field_n"] >= min_field)]


def regulars(zones: pd.DataFrame) -> pd.DataFrame:
    """Drop drivers with fewer than MIN_ZONES zones."""
    counts = zones["driver"].value_counts()
    return zones[zones["driver"].map(counts) >= MIN_ZONES]


def bootstrap_median(values: np.ndarray, n: int = 2000, seed: int = 0):
    """Median and 95 % bootstrap interval."""
    rng = np.random.default_rng(seed)
    values = np.asarray(values, dtype=float)
    draws = rng.choice(values, size=(n, values.size), replace=True)
    lo, hi = np.percentile(np.median(draws, axis=1), [2.5, 97.5])
    return float(np.median(values)), float(lo), float(hi)


def _hatch_missing(ax) -> None:
    """Missing cells show a diagonal hatch, not a grey that reads as zero."""
    ax.set_facecolor(style.SURFACE)
    ax.add_patch(
        plt.Rectangle(
            (0, 0),
            1,
            1,
            transform=ax.transAxes,
            facecolor=style.SURFACE,
            edgecolor=style.GRID,
            hatch="////",
            linewidth=0,
            zorder=0,
        )
    )


def _corner_order(zones: pd.DataFrame) -> list[str]:
    return list(zones.groupby("corner")["mark_distance"].median().sort_values().index)


def _braking_segments(track: pd.DataFrame, marks: pd.DataFrame, zones: pd.DataFrame):
    """Track polyline pieces from the field's median brake point to each mark.

    Distances are on the reference lap's own axis: the mark position
    comes from projecting the mark onto that lap, the brake point is the
    field median of metres before the mark.
    """
    d = track["Distance"].to_numpy(dtype=float)
    x = track["X"].to_numpy(dtype=float)
    y = track["Y"].to_numpy(dtype=float)
    stats = zones.groupby("corner").agg(
        before=("bp_before_mark", "median"), peak=("peak_decel_g", "median")
    )
    out = []
    for _, mark in marks.iterrows():
        if mark["Name"] not in stats.index:
            continue
        before, peak = stats.loc[mark["Name"]]
        sel = (d >= mark["Distance"] - before) & (d <= mark["Distance"])
        if sel.sum() >= 2:
            out.append((np.column_stack([x[sel], y[sel]]), peak, mark))
    return out


def track_map(ax, track, marks, zones, vmax=5.0, labels=True, width=4.0):
    """Grey track outline with the field's braking zones drawn on it."""
    ax.plot(
        track["X"],
        track["Y"],
        color=style.GRID,
        linewidth=width * 0.6,
        solid_capstyle="round",
        zorder=1,
    )
    segs = _braking_segments(track, marks, zones)
    lines = LineCollection(
        [s for s, _, _ in segs],
        cmap=style.magnitude_cmap(),
        linewidths=width,
        capstyle="round",
        zorder=2,
    )
    lines.set_array(np.array([p for _, p, _ in segs]))
    lines.set_clim(1.0, vmax)
    ax.add_collection(lines)
    if labels:
        for _, _, mark in segs:
            ax.annotate(
                mark["Name"],
                (mark["X"], mark["Y"]),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=7,
                color=style.INK_2,
            )
    # A square box with equal scaling: every track fills the same panel
    # size, so titles in a grid line up whatever the circuit's shape.
    ax.set_box_aspect(1)
    ax.set_aspect("equal", adjustable="datalim")
    ax.autoscale()
    ax.margins(0.04)
    ax.set_axis_off()
    return lines


def session_heatmap(zones: pd.DataFrame, limit: float = 30.0):
    """Drivers (qualifying order) by corners (track order), brake-point delta."""
    z = heavy(zones, min_field=8)
    order = _corner_order(z)
    drivers = z.sort_values("rank").drop_duplicates("driver")["driver"].tolist()
    grid = z.pivot_table(index="driver", columns="corner", values=METRIC)
    grid = grid.reindex(index=drivers, columns=order)

    fig, ax = plt.subplots(
        figsize=(max(7.5, 2.5 + 0.62 * len(order)), 1.2 + 0.27 * len(drivers))
    )
    _hatch_missing(ax)
    im = ax.imshow(
        grid.to_numpy(),
        cmap=style.delta_cmap(),
        norm=style.delta_norm(limit),
        aspect="auto",
    )
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(range(len(order)), order)
    ax.set_yticks(range(len(drivers)), drivers)
    ax.xaxis.tick_top()
    cb = fig.colorbar(im, ax=ax, shrink=0.6, pad=0.02)
    cb.outline.set_visible(False)
    cb.set_label(LABEL)
    return fig, ax


def track_grid(
    tracks: pd.DataFrame,
    marks: pd.DataFrame,
    zones: pd.DataFrame,
    order: list[str],
    ncols: int = 6,
):
    """Small multiples: every circuit with its braking zones, same colour scale."""
    nrows = int(np.ceil(len(order) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(2.1 * ncols, 2.2 * nrows))
    lines = None
    for ax, name in zip(axes.flat, order, strict=False):
        lines = track_map(
            ax,
            tracks[tracks["track"] == name],
            marks[marks["track"] == name],
            heavy(zones[zones["track"] == name]),
            labels=False,
            width=2.6,
        )
        n = heavy(zones[zones["track"] == name])["corner"].nunique()
        ax.set_title(f"{name}  ·  {n}", fontsize=8, color=style.INK, loc="left")
    for ax in axes.flat[len(order) :]:
        ax.set_axis_off()
    cb = fig.colorbar(lines, ax=axes, shrink=0.35, pad=0.01, aspect=25)
    cb.outline.set_visible(False)
    cb.set_label("Field median peak deceleration [g]")
    return fig, axes


def season_heatmap(zones: pd.DataFrame, track_order: list[str], limit: float = 15.0):
    """Drivers by tracks: median brake-point delta over the track's heavy zones."""
    z = regulars(heavy(zones))
    per = z.groupby(["driver", "track"])[METRIC].median().unstack()
    season = z.groupby("driver")[METRIC].median().sort_values(ascending=False)
    per = per.reindex(index=season.index, columns=track_order)

    fig, ax = plt.subplots(
        figsize=(1.6 + 0.42 * len(track_order), 1.0 + 0.27 * len(per))
    )
    _hatch_missing(ax)
    im = ax.imshow(
        per.to_numpy(),
        cmap=style.delta_cmap(),
        norm=style.delta_norm(limit),
        aspect="auto",
    )
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(range(len(track_order)), track_order, rotation=60, ha="left")
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(per)), [f"{d}  {season[d]:+.1f}" for d in per.index])
    cb = fig.colorbar(im, ax=ax, shrink=0.5, pad=0.02)
    cb.outline.set_visible(False)
    cb.set_label(LABEL)
    return fig, ax


def driver_index(zones: pd.DataFrame, teams: dict[str, str]):
    """Season median brake-point delta per driver with 95 % intervals."""
    z = regulars(heavy(zones))
    rows = []
    for driver, g in z.groupby("driver"):
        med, lo, hi = bootstrap_median(g[METRIC].dropna().to_numpy())
        rows.append((driver, med, lo, hi, len(g)))
    t = pd.DataFrame(rows, columns=["driver", "med", "lo", "hi", "n"])
    t = t.sort_values("med").reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(7.5, 0.9 + 0.28 * len(t)))
    y = np.arange(len(t))
    ax.hlines(y, t["lo"], t["hi"], color=style.SERIES[0], linewidth=1.6)
    ax.plot(t["med"], y, "o", color=style.SERIES[0], markersize=5)
    ax.axvline(0.0, color=style.INK_2, linewidth=0.6)
    ax.set_yticks(y, [f"{d}  ({teams.get(d, '')})" for d in t["driver"]])
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlabel(LABEL + ", season median")
    return fig, ax, t


def pace_scatter(index: pd.DataFrame, pace: pd.Series):
    """Late-braking index against qualifying pace, one point per driver.

    index: output table of driver_index (driver, med, lo, hi).
    pace: median gap to pole [%] per driver.
    """
    t = index.set_index("driver").join(pace.rename("pace"), how="inner")
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    ax.hlines(t["pace"], t["lo"], t["hi"], color=style.GRID, linewidth=1.2)
    ax.plot(t["med"], t["pace"], "o", color=style.SERIES[0], markersize=5)
    for d, row in t.iterrows():
        # A neighbour just to the right would collide: label on the left.
        crowded = (
            (t["med"] > row["med"])
            & (t["med"] - row["med"] < 0.8)
            & ((t["pace"] - row["pace"]).abs() < 0.08)
        ).any()
        ax.annotate(
            d,
            (row["med"], row["pace"]),
            xytext=(-4, 3) if crowded else (4, 3),
            ha="right" if crowded else "left",
            textcoords="offset points",
            fontsize=7,
            color=style.INK_2,
        )
    ax.axvline(0.0, color=style.INK_2, linewidth=0.6)
    ax.invert_yaxis()
    ax.grid(axis="x", visible=True)
    ax.set_xlabel(LABEL)
    ax.set_ylabel("Median gap to pole [%]  (faster up)")
    return fig, ax, t


def teammate_pairs(zones: pd.DataFrame) -> pd.DataFrame:
    """Paired teammate differences: same session, same corner, both present.

    Returns one row per regular pairing with the median difference
    (second driver minus first, alphabetical) and a 95 % bootstrap
    interval. Pairing cancels the car, the track and the session.
    """
    z = regulars(heavy(zones))
    rows = []
    for (_, _, team), g in z.groupby(["session", "corner", "team"]):
        if len(g) == 2:
            a, b = sorted(g["driver"])
            v = g.set_index("driver")[METRIC]
            rows.append((team, a, b, v[b] - v[a]))
    diffs = pd.DataFrame(rows, columns=["team", "a", "b", "diff"])
    out = []
    for (team, a, b), g in diffs.groupby(["team", "a", "b"]):
        if len(g) >= MIN_ZONES:
            med, lo, hi = bootstrap_median(g["diff"].dropna().to_numpy())
            out.append((team, a, b, med, lo, hi, len(g)))
    return pd.DataFrame(out, columns=["team", "a", "b", "med", "lo", "hi", "n"])


def teammates(pairs: pd.DataFrame):
    """One row per team: how much later the second driver brakes."""
    t = pairs.sort_values("med").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(7.5, 0.9 + 0.38 * len(t)))
    y = np.arange(len(t))
    ax.axvspan(-2.0, 2.0, color=style.NEUTRAL, zorder=0)
    ax.hlines(y, t["lo"], t["hi"], color=style.SERIES[0], linewidth=1.6)
    ax.plot(t["med"], y, "o", color=style.SERIES[0], markersize=5)
    ax.axvline(0.0, color=style.INK_2, linewidth=0.6)
    ax.set_yticks(y, [f"{r.b} vs {r.a}  ({r.team})" for r in t.itertuples()])
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlabel(
        "How much later the first-named driver brakes, same corner and session [m]"
    )
    return fig, ax


def coast_by_round(zones: pd.DataFrame, order: list[str], min_coast: float = 40.0):
    """Share of heavy stops preceded by a clear lift and coast, per round."""
    z = heavy(zones)
    share = (z["coast_before"] >= min_coast).groupby(z["track"]).mean().reindex(
        order
    ) * 100
    fig, ax = plt.subplots(figsize=(8.5, 3.6))
    x = np.arange(len(order))
    ax.bar(x, share.to_numpy(), width=0.7, color=style.SERIES[0])
    ax.set_xticks(x, order, rotation=60, ha="right")
    ax.set_ylabel(f"Heavy stops after ≥{min_coast:.0f} m of coasting [%]")
    ax.set_xlim(-0.6, len(order) - 0.4)
    return fig, ax, share
