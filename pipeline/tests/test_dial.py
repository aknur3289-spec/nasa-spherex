"""Runtime build and science regression for the synthetic distance dial."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from spx.contract_check import validate_field  # noqa: E402


def test_runtime_dial_build(tmp_path):
    output_root = tmp_path / "out"
    command = [sys.executable, str(ROOT / "pipeline" / "build_dial.py"),
               "--id", "neptune-test", "--body", "neptune", "--t0", "2025-06-10",
               "--dt-days", "182.6", "--dmin", "15", "--dmax", "1000", "--step-px", "15",
               "--provider", "synthetic", "--out", str(output_root)]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)

    field_dir = output_root / "neptune-test"
    field = json.loads((field_dir / "field.json").read_text())
    summary = json.loads((field_dir / "summary.json").read_text())
    assert validate_field(field, field_dir=field_dir) == []
    assert field["provenance"]["synthetic"] is True

    truth = summary["truth_distance_au"]
    circular = summary["runs"]["circular"]
    assert abs(circular["peak_distance_au"] - truth) / truth <= 0.15
    assert circular["peak_over_median"] >= 3
    assert summary["runs"]["empty_sky_control"]["peak_over_median"] < 3
    static = summary["runs"]["static_baseline"]
    assert abs(static["peak_distance_au"] - truth) / truth > 0.15
