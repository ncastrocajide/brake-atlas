"""Official corner marks per circuit, from the MultiViewer API.

The same reference data FastF1 shows as circuit info: corner number and
map position. Requests go through FastF1's own MultiViewer client (the
API is provided to FastF1 by MultiViewer), and the raw answer is kept
in the project cache. OpenF1's circuit_key is the key this API expects.
Positions come in 1/10 m, like the position stream.
"""

import json

import pandas as pd
from fastf1.mvapi.api import get_circuit

from brakeatlas.openf1 import OpenF1


def corner_marks(client: OpenF1, circuit_key: int, year: int) -> pd.DataFrame:
    """Corner marks with Name ("T4"), Number and X, Y in metres."""
    path = client.cache_dir / f"circuit_{circuit_key}_{year}.json"
    if path.exists():
        info = json.loads(path.read_text())
    else:
        info = get_circuit(year=year, circuit_key=circuit_key)
        if info is None:
            raise ValueError(f"no circuit info for key {circuit_key}, {year}")
        path.write_text(json.dumps(info))
    rows = [
        {
            "Name": f"T{c['number']}{c.get('letter') or ''}",
            "Number": int(c["number"]),
            "X": c["trackPosition"]["x"] / 10.0,
            "Y": c["trackPosition"]["y"] / 10.0,
        }
        for c in info["corners"]
    ]
    return pd.DataFrame(rows)
