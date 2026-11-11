"""Braking-zone extraction: turn one lap into a list of braking events.

A braking zone starts where the brake channel rises above a threshold
and ends at the speed minimum that braking leads to. Everything is
measured on the canonical distance grid of an apextrace Lap, so zones
from different drivers on the same track can be lined up metre by metre.

Deceleration comes from the speed trace, not from the brake channel:
on a distance grid a = v * dv/ds, which needs no time derivative. F1
timing data has a near on/off brake signal, so the speed trace is the
only measure of how hard a driver brakes. No smoothing is applied here;
any smoothing must be declared by the caller, never hidden inside
detection (the same house rule as apextrace.corners).

Sampling caveat: FastF1 car data arrives every ~0.2-0.27 s, which is up
to ~20 m at 300 km/h. Brake points are therefore located to within one
raw sample; the 5 m grid does not add information it never had.
"""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from apextrace.lap import Lap

G = 9.81  # m/s^2


@dataclass
class BrakeZone:
    """One braking event. Distances in metres from the line.

    coast_before is the distance travelled off throttle and off brake
    right before the brake point: lift-and-coast, the signature of
    energy management (harvesting) or fuel saving.
    release_offset is release_point - min_speed_point: negative means
    the brake came off before the speed minimum (the car rolls to the
    apex), near zero means braking all the way down, which on an on/off
    signal is the closest proxy for trail braking.
    """

    number: int  # 1-based, in track order
    brake_point: float  # first brake application [m]
    release_point: float  # last brake sample of the zone [m]
    min_speed_point: float  # speed minimum reached after braking [m]
    entry_speed: float  # speed at the brake point [km/h]
    min_speed: float  # [km/h]
    speed_drop: float  # entry_speed - min_speed [km/h]
    braking_distance: float  # brake_point to min_speed_point [m]
    mean_decel_g: float  # energy-equivalent mean deceleration [g]
    peak_decel_g: float  # max deceleration over the zone [g]
    release_offset: float  # release_point - min_speed_point [m]
    coast_before: float  # off-throttle, off-brake run before braking [m]
    corner: str | None = None  # official designation, filled by a later pass


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Inclusive (start, end) index pairs of contiguous True runs."""
    edges = np.diff(np.concatenate(([0], mask.astype(int), [0])))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1) - 1
    return list(zip(starts.tolist(), ends.tolist(), strict=True))


def detect_brake_zones(
    lap: Lap,
    brake_threshold: float = 10.0,
    throttle_threshold: float = 95.0,
    merge_gap: float = 20.0,
    min_speed_drop: float = 10.0,
    rise_tol: float = 2.0,
) -> list[BrakeZone]:
    """Extract the braking zones of a lap.

    brake_threshold: Brake % above which the driver is braking.
    throttle_threshold: Throttle % below which the driver is off throttle
        (used for coast_before).
    merge_gap: brake runs separated by less than this [m] are one zone
        (signal flicker or a re-application mid-zone).
    min_speed_drop: zones that lose less than this [km/h] are dabs or
        stabilising touches, not braking zones, and are discarded.
    rise_tol: speed gain above the running minimum [km/h] that marks the
        car accelerating away, ending the search for the zone's minimum.
        Keeps sampling ripple from cutting a zone short.
    """
    data = lap.data
    dist = data["Distance"].to_numpy(dtype=float)
    speed = data["Speed"].to_numpy(dtype=float)
    brake = data["Brake"].to_numpy(dtype=float)
    throttle = data["Throttle"].to_numpy(dtype=float)
    step = float(dist[1] - dist[0])

    runs = _runs(brake > brake_threshold)
    merged: list[tuple[int, int]] = []
    for start, end in runs:
        if merged and (start - merged[-1][1]) * step < merge_gap:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))

    # Longitudinal acceleration on the distance grid: a = v dv/ds [m/s^2].
    v = speed / 3.6
    accel = v * np.gradient(v, dist)

    zones: list[BrakeZone] = []
    for k, (start, end) in enumerate(merged):
        # The speed minimum can come after brake release (rolling to the
        # apex), so search up to the next zone, or to the end of the lap,
        # but stop once the car is clearly accelerating away: a later,
        # slower corner must not be claimed by this zone.
        limit = merged[k + 1][0] if k + 1 < len(merged) else dist.size
        window = speed[start:limit]
        recovered = np.flatnonzero(window - np.minimum.accumulate(window) > rise_tol)
        if recovered.size:
            window = window[: recovered[0]]
        i_min = start + int(np.argmin(window))

        drop = float(speed[start] - speed[i_min])
        if drop < min_speed_drop or i_min == start:
            continue

        d_brake = float(dist[i_min] - dist[start])
        v_e, v_m = v[start], v[i_min]

        # Walk back from the brake point while off throttle and off brake.
        j = start - 1
        while (
            j >= 0 and throttle[j] < throttle_threshold and brake[j] <= brake_threshold
        ):
            j -= 1
        coast = float(dist[start] - dist[j + 1]) if j + 1 < start else 0.0

        zones.append(
            BrakeZone(
                number=len(zones) + 1,
                brake_point=float(dist[start]),
                release_point=float(dist[end]),
                min_speed_point=float(dist[i_min]),
                entry_speed=float(speed[start]),
                min_speed=float(speed[i_min]),
                speed_drop=drop,
                braking_distance=d_brake,
                mean_decel_g=float((v_e**2 - v_m**2) / (2.0 * d_brake) / G),
                peak_decel_g=float(-accel[start : i_min + 1].min() / G),
                release_offset=float(dist[end] - dist[i_min]),
                coast_before=coast,
            )
        )
    return zones


def zones_to_frame(zones: list[BrakeZone], **tags: object) -> pd.DataFrame:
    """Tidy table of zones, one row each, with constant tag columns.

    Tags carry the context the zone itself does not know (driver, team,
    track, session, lap), so tables from many laps can be concatenated
    into one field-wide dataset.
    """
    frame = pd.DataFrame([asdict(z) for z in zones])
    for key, value in tags.items():
        frame.insert(0, key, value)
    return frame
