"""Put every driver's braking zones on the same footing.

Each lap measures the track with its own integrated odometer, so raw
brake points disagree by metres before any driver difference shows.
Instead of comparing raw distances, each zone is tied to the official
corner it serves, and the brake point is measured as metres before
that corner's mark on the lap's own distance axis. Odometer drift
cancels, because mark and brake point share the same axis.
"""

import numpy as np
import pandas as pd
from apextrace.corners import locate_marks
from apextrace.lap import Lap

from brakeatlas.zones import detect_brake_zones, zones_to_frame

SEG_BEFORE, SEG_AFTER = 250.0, 150.0  # corner segment around the mark [m]


def scaled_marks(marks: pd.DataFrame, ref_length: float, lap: Lap) -> pd.DataFrame:
    """Marks located on a reference lap, moved onto another lap's axis.

    For laps without position data (race laps are fetched without it).
    Each lap's odometer runs slightly long or short, so mark distances
    are scaled by the ratio of lap lengths.
    """
    out = marks[["Name", "Distance"]].copy()
    out["Distance"] *= float(lap.data["Distance"].iloc[-1]) / ref_length
    return out


def field_marks(
    marks: pd.DataFrame, ref_length: float, zones: pd.DataFrame
) -> pd.DataFrame:
    """Reference marks with each corner moved to the field's median position.

    marks: Name and Distance on one reference lap. A single lap can have
    a telemetry dropout that shifts its distance axis locally (seen at
    Monza T4: 22 m). Where the qualifying zones give a corner's position
    for several drivers, the median of mark_distance / lap_length over
    them replaces the reference lap's value.
    """
    frac = (zones["mark_distance"] / zones["lap_length"]).groupby(zones["corner"])
    frac = frac.median()[frac.size() >= 5]
    out = marks[["Name", "Distance"]].copy()
    better = out["Name"].map(frac) * ref_length
    out["Distance"] = better.fillna(out["Distance"])
    return out


def lap_zones(
    lap: Lap,
    marks: pd.DataFrame,
    max_before: float = 400.0,
    gap_margin: float = 50.0,
    located: bool = False,
    **tags: object,
) -> pd.DataFrame:
    """Braking zones of one lap, labelled with the corner they serve.

    A zone serves the first corner mark after its brake point, if that
    mark is within max_before metres. Using the brake point rather than
    the speed minimum keeps chicanes consistent: the minimum can fall
    on either apex, the brake point is always before the first one.
    When two zones claim the same corner, the one with the larger speed
    drop is kept. Zones overlapping a telemetry dropout (gaps_m in the
    lap attrs, widened by gap_margin) are dropped.

    located: True when `marks` already has a Distance column on this
        lap's axis (see scaled_marks), so no X/Y projection is needed.

    Adds mark_distance, bp_before_mark (mark minus brake point [m],
    smaller = later braking), lap_length, seg_time (seconds from 250 m
    before the mark to 150 m after it, NaN if that runs off the lap)
    and, when the lap carries raw sample positions, bp_uncertainty_m:
    half the spacing of the raw samples around the brake point.
    """
    frame = zones_to_frame(detect_brake_zones(lap), **tags)
    if frame.empty:
        return frame
    placed = marks if located else locate_marks(lap, marks)
    placed = placed.sort_values("Distance")
    mark_d = placed["Distance"].to_numpy(dtype=float)
    names = placed["Name"].to_numpy()

    bp = frame["brake_point"].to_numpy(dtype=float)
    idx = np.searchsorted(mark_d, bp, side="left")
    found = idx < mark_d.size
    idx = np.clip(idx, 0, mark_d.size - 1)
    ahead = mark_d[idx] - bp
    ok = found & (ahead <= max_before)
    frame["corner"] = np.where(ok, names[idx], None)
    frame["mark_distance"] = mark_d[idx]
    frame = frame[frame["corner"].notna()]

    for start, end in lap.data.attrs.get("gaps_m", []):
        hit = (frame["brake_point"] - gap_margin < end) & (
            frame["min_speed_point"] + gap_margin > start
        )
        frame = frame[~hit]

    frame = frame.sort_values("speed_drop", ascending=False)
    frame = frame.drop_duplicates("corner").sort_values("brake_point")
    frame["bp_before_mark"] = frame["mark_distance"] - frame["brake_point"]

    dist = lap.data["Distance"].to_numpy(dtype=float)
    time = lap.data["Time"].to_numpy(dtype=float)
    frame["lap_length"] = dist[-1]
    seg_in = frame["mark_distance"].to_numpy() - SEG_BEFORE
    seg_out = frame["mark_distance"].to_numpy() + SEG_AFTER
    seg = np.interp(seg_out, dist, time) - np.interp(seg_in, dist, time)
    frame["seg_time"] = np.where((seg_in >= 0.0) & (seg_out <= dist[-1]), seg, np.nan)

    sample_d = np.asarray(lap.data.attrs.get("sample_d", []), dtype=float)
    if sample_d.size > 1:
        i = np.clip(
            np.searchsorted(sample_d, frame["brake_point"]), 1, sample_d.size - 1
        )
        frame["bp_uncertainty_m"] = (sample_d[i] - sample_d[i - 1]) / 2.0
    return frame.reset_index(drop=True)


def field_deltas(
    zones: pd.DataFrame, by=("session", "corner"), min_fit: int = 8
) -> pd.DataFrame:
    """Add each zone's position relative to the field at that corner.

    bp_delta_m: field median of bp_before_mark minus this driver's
        value, so positive = brakes later than the median [m].
    bp_delta_ms: the same converted to time at entry speed [ms].
    bp_z: bp_delta_m over the field's MAD scaled to a standard
        deviation (1.4826 * MAD); comparable between corners.
    vmin_delta: minimum speed minus the field median [km/h].
    bp_resid_m: brake-point delta corrected for entry speed [m],
        positive = later than expected. A car that arrives slower can
        brake later without the driver doing anything special, since
        stopping distance grows with v^2. At each corner bp_before_mark
        is fitted against entry_speed^2 over the field (least squares,
        min_fit drivers or more) and the residual is kept. NaN where
        too few drivers have data.
    """
    out = zones.copy()
    groups = out.groupby(list(by))
    med_bp = groups["bp_before_mark"].transform("median")
    out["bp_delta_m"] = med_bp - out["bp_before_mark"]
    out["bp_delta_ms"] = out["bp_delta_m"] / (out["entry_speed"] / 3.6) * 1000.0
    mad = groups["bp_before_mark"].transform(lambda s: (s - s.median()).abs().median())
    out["bp_z"] = out["bp_delta_m"] / (1.4826 * mad.replace(0.0, np.nan))
    out["vmin_delta"] = out["min_speed"] - groups["min_speed"].transform("median")
    out["field_n"] = groups["bp_before_mark"].transform("size")

    out["bp_resid_m"] = np.nan
    for _, g in groups:
        if len(g) < min_fit:
            continue
        v2 = (g["entry_speed"].to_numpy() / 3.6) ** 2
        bp = g["bp_before_mark"].to_numpy()
        slope, icpt = np.polyfit(v2, bp, 1)
        out.loc[g.index, "bp_resid_m"] = (icpt + slope * v2) - bp
    return out
