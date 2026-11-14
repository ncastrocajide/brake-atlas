"""Load laps from the OpenF1 API (api.openf1.org) as apextrace Laps.

OpenF1 serves the same car and position feeds as the official timing
(about 4 Hz, brake on/off) and, unlike the F1 archive since October
2026, needs no account for past sessions. Every response is cached on
disk, so a session is downloaded once.

Distance is integrated from speed over time, like FastF1's
add_distance. Each lap therefore carries its own small odometer error;
field-level code rescales laps to a common length before comparing.
"""

import gzip
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from apextrace.lap import Lap, resample_to_distance

API = "https://api.openf1.org/v1/"
CACHE_DIR = Path(__file__).resolve().parents[1] / ".openf1_cache"


class OpenF1:
    """Minimal client: GET with an on-disk JSON cache and a polite pace."""

    def __init__(self, cache_dir: Path = CACHE_DIR, pause: float = 0.4):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.pause = pause

    def get(self, endpoint: str, **params) -> list[dict]:
        query = urllib.parse.urlencode(params, safe=":")
        # OpenF1 filters are written as key>=value; urlencode would put
        # the operator in the key, so build those by hand.
        query = query.replace("%3E%3D=", ">=").replace("%3C%3D=", "<=")
        return self.get_url(f"{API}{endpoint}?{query}")

    def get_url(self, url: str):
        """GET any JSON URL through the same cache and pacing."""
        key = hashlib.sha1(url.encode()).hexdigest()
        path = self.cache_dir / f"{key}.json.gz"
        plain = self.cache_dir / f"{key}.json"  # caches written before gzip
        if plain.exists():
            return json.loads(plain.read_text())
        if path.exists():
            return json.loads(gzip.decompress(path.read_bytes()))

        for attempt in range(5):
            try:
                with urllib.request.urlopen(url, timeout=120) as resp:
                    data = json.loads(resp.read())
                break
            except urllib.error.HTTPError as err:
                if err.code == 404:  # OpenF1 answers 404 for "no rows"
                    data = []
                    break
                if err.code != 429 or attempt == 4:
                    raise
                time.sleep(2.0 * 2**attempt)
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                # Dropped connections happen on long runs; retry the same way.
                if attempt == 4:
                    raise
                time.sleep(2.0 * 2**attempt)
        time.sleep(self.pause)
        path.write_bytes(gzip.compress(json.dumps(data).encode()))
        return data


def _when(text: str) -> datetime:
    return datetime.fromisoformat(text)


def session_laps(client: OpenF1, session_key: int) -> pd.DataFrame:
    """Lap table of a session with driver acronym and team attached."""
    laps = pd.DataFrame(client.get("laps", session_key=session_key))
    drivers = pd.DataFrame(client.get("drivers", session_key=session_key))
    drivers = drivers[["driver_number", "name_acronym", "team_name"]]
    drivers = drivers.drop_duplicates("driver_number")
    return laps.merge(drivers, on="driver_number", how="left")


def fastest_laps(laps: pd.DataFrame) -> pd.DataFrame:
    """Each driver's fastest timed lap that is not an out-lap."""
    timed = laps[laps["lap_duration"].notna() & ~laps["is_pit_out_lap"].astype(bool)]
    idx = timed.groupby("driver_number")["lap_duration"].idxmin()
    return timed.loc[idx].sort_values("lap_duration").reset_index(drop=True)


def _seconds(dates: pd.Series) -> np.ndarray:
    """ISO timestamps as seconds since the Unix epoch."""
    stamps = pd.to_datetime(dates, format="ISO8601", utc=True)
    return (stamps - pd.Timestamp(0, tz="UTC")).dt.total_seconds().to_numpy()


def car_samples(
    client: OpenF1, session_key: int, driver_number: int, start: datetime, end: datetime
) -> pd.DataFrame:
    """Raw car data of one driver between two instants, with a "t" column.

    t is seconds since the Unix epoch. One call can cover a whole race
    (about 27 000 rows), which is far cheaper than one call per lap.
    """
    car = pd.DataFrame(
        client.get(
            "car_data",
            session_key=session_key,
            driver_number=driver_number,
            **{"date>=": start.isoformat(), "date<=": end.isoformat()},
        )
    )
    if not car.empty:
        car["t"] = _seconds(car["date"])
    return car


def build_lap(
    car: pd.DataFrame,
    t_start: float,
    lap_duration: float,
    label: str,
    pos: pd.DataFrame | None = None,
    step: float = 5.0,
    max_gap: float = 0.6,
) -> Lap:
    """Cut one lap out of raw car samples and put it on a distance grid.

    car, pos: raw samples with a "t" column in seconds, same origin as
    t_start. The feed sometimes freezes: speed stops updating and
    throttle and brake read 104. Those samples are dropped. Where valid
    samples are more than `max_gap` seconds apart, the interval is
    stored in lap.data.attrs["gaps_m"] as (start, end) distances, so
    braking zones inside a dropout can be excluded instead of measured.
    """
    near = (car["t"] >= t_start - 2.0) & (car["t"] <= t_start + lap_duration + 2.0)
    car = car[near & (car["throttle"] <= 100) & (car["brake"] <= 100)]
    if len(car) < 2:
        raise ValueError(f"no car data for {label}")
    t_car = car["t"].to_numpy(dtype=float) - t_start
    inside = (t_car >= 0.0) & (t_car <= lap_duration)
    t_grid = np.concatenate(([0.0], t_car[inside], [lap_duration]))

    def channel(name: str) -> np.ndarray:
        return np.interp(t_grid, t_car, car[name].to_numpy(dtype=float))

    speed = channel("speed")
    dist = np.concatenate(
        ([0.0], np.cumsum(np.diff(t_grid) * (speed[1:] + speed[:-1]) / 2.0 / 3.6))
    )
    raw = pd.DataFrame(
        {
            "Distance": dist,
            "Time": t_grid,
            "Speed": speed,
            "Throttle": channel("throttle"),
            "Brake": channel("brake"),
            # Gear is discrete: take the nearest earlier sample, not a blend.
            "Gear": car["n_gear"].to_numpy(dtype=float)[
                np.clip(np.searchsorted(t_car, t_grid, side="right") - 1, 0, None)
            ],
            "RPM": channel("rpm"),
        }
    )
    if pos is not None and not pos.empty:
        t_pos = pos["t"].to_numpy(dtype=float) - t_start
        for axis in ("x", "y"):
            # Position comes in 1/10 m, like the FastF1 position stream.
            raw[axis.upper()] = (
                np.interp(t_grid, t_pos, pos[axis].to_numpy(dtype=float)) / 10.0
            )

    lap = Lap(
        data=resample_to_distance(raw, step=step),
        label=label,
        source="openf1",
    )
    # Raw sample positions, so callers can tell how well a brake point
    # is pinned down (half the spacing of the samples around it).
    lap.data.attrs["sample_d"] = dist.tolist()
    wide = np.flatnonzero(np.diff(t_grid) > max_gap)
    lap.data.attrs["gaps_m"] = [(float(dist[i]), float(dist[i + 1])) for i in wide]
    return lap


def load_lap(
    client: OpenF1,
    session_key: int,
    driver_number: int,
    date_start: str,
    lap_duration: float,
    label: str,
    step: float = 5.0,
    max_gap: float = 0.6,
) -> Lap:
    """Fetch one timed lap (car data and position) as a canonical Lap."""
    t0 = _when(date_start)
    # Fetch a little either side so the lap ends can be interpolated.
    start = t0 - timedelta(seconds=2)
    end = t0 + timedelta(seconds=lap_duration + 2)
    car = car_samples(client, session_key, driver_number, start, end)
    if car.empty:
        raise ValueError(f"no car data for driver {driver_number} in {label}")
    pos = pd.DataFrame(
        client.get(
            "location",
            session_key=session_key,
            driver_number=driver_number,
            **{"date>=": start.isoformat(), "date<=": end.isoformat()},
        )
    )
    if not pos.empty:
        pos["t"] = _seconds(pos["date"])
    return build_lap(
        car, t0.timestamp(), lap_duration, label, pos=pos, step=step, max_gap=max_gap
    )
