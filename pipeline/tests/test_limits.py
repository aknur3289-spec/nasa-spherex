"""Contract checks for the generated detectability panel data."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "out" / "limits.json"


def _data():
    if not DATA_PATH.exists():
        subprocess.run([sys.executable, str(ROOT / "pipeline" / "build_limits.py")], check=True)
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def test_limits_json_has_required_keys():
    data = _data()
    assert set(data) == {"schema", "model", "caveats", "single_frame_limit_ab", "limits",
                         "distances_au", "bodies", "planet_nine_literature"}
    assert data["schema"] == "limits-1.0"
    assert set(data["limits"]) == {"1", "4", "100", "300"}
    assert len(data["distances_au"]) == 60
    assert set(data["planet_nine_literature"]) == {"V_range", "source"}
    for body in data["bodies"]:
        assert set(body) == {"name", "diameter_km", "albedo", "H", "mag", "max_d_au"}
        assert len(body["mag"]) == len(data["distances_au"])
        assert set(body["max_d_au"]) == {"1", "100", "300"}


def test_neptune_single_frame_distance():
    body = next(b for b in _data()["bodies"] if b["name"] == "Neptune-size")
    assert 300 <= body["max_d_au"]["1"] <= 380


def test_magnitudes_strictly_increase_with_distance():
    for body in _data()["bodies"]:
        assert np.all(np.diff(body["mag"]) > 0)


def test_max_distance_grows_with_frame_count():
    for body in _data()["bodies"]:
        distances = body["max_d_au"]
        assert distances["1"] < distances["100"] < distances["300"]
