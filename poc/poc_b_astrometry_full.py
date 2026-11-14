#!/usr/bin/env python
"""Full local-cutout, all-pairs real SPHEREx astrometric fits."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from poc_b_astrometry import _check_time, _fit_local_grid, _measure_local_cutout, _stats

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "poc" / "out"


def run_full(body: str, data_root: Path) -> dict:
    metadata = data_root / "data" / "meta" / body / "epochs.csv"
    if not metadata.is_file():
        raise FileNotFoundError(f"metadata CSV not found: {metadata}")
    with metadata.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    available_status = {"ok"} if body == "neptune" else {"ok", "cached"}
    candidates = {"1": [], "2": []}
    skipped = []
    for row in rows:
        window = str(row.get("window_id", ""))
        if window not in candidates:
            continue
        try:
            bad_frac = float(row.get("bad_frac", ""))
        except (TypeError, ValueError):
            bad_frac = float("inf")
        if row.get("status") not in available_status:
            skipped.append({"obs_id": row.get("obs_id"), "window_id": window,
                            "reason": f"status={row.get('status')}"})
            continue
        if bad_frac > 0.5:
            skipped.append({"obs_id": row.get("obs_id"), "window_id": window,
                            "reason": f"bad_frac={bad_frac}"})
            continue
        if row.get("inside", "True").strip().lower() not in {"true", "1", "yes"}:
            skipped.append({"obs_id": row.get("obs_id"), "window_id": window,
                            "reason": "inside=false"})
            continue
        local_path = data_root / str(row.get("local_path", ""))
        if not local_path.is_file():
            skipped.append({"obs_id": row.get("obs_id"), "window_id": window,
                            "reason": f"missing_local_file={local_path}"})
            continue
        candidates[window].append(row)

    exposures = {"1": [], "2": []}
    errors = []
    for window in ("1", "2"):
        for index, row in enumerate(candidates[window], 1):
            _check_time()
            try:
                measured = _measure_local_cutout(row, data_root)
                if row.get("eph_r") not in (None, ""):
                    measured["eph_r"] = float(row["eph_r"])
                exposures[window].append(measured)
            except Exception as exc:
                errors.append({"obs_id": row["obs_id"], "window_id": window,
                               "error": f"{type(exc).__name__}: {exc}"})
            if index % 10 == 0:
                print(f"{body.title()} window {window}: {index}/{len(candidates[window])} cutouts measured")
        exposures[window].sort(key=lambda row: (row["mjd"], row["detector"]))
    if not exposures["1"] or not exposures["2"]:
        raise RuntimeError(f"No measurements in both epochs: A={len(exposures['1'])} B={len(exposures['2'])}")

    if body == "neptune":
        with (ROOT / "poc" / "windows_neptune.csv").open(newline="") as stream:
            window_rows = {str(row["window_id"]): row for row in csv.DictReader(stream)}
        truth = float(np.mean([float(window_rows["1"]["r_au"]),
                               float(window_rows["2"]["r_au"])]))
        truth_source = "mean r_au in poc/windows_neptune.csv, windows 1 and 2"
    else:
        truth_a = [float(row["eph_r"]) for row in exposures["1"]]
        truth_b = [float(row["eph_r"]) for row in exposures["2"]]
        truth = float(np.mean([np.mean(truth_a), np.mean(truth_b)]))
        truth_source = "mean of mean Horizons eph_r values among measured exposures in each epoch"
    d_grid = np.geomspace(15.0, 1000.0, 1800)
    print(f"{body.title()} full fit grid: geomspace 15–1000 AU, 1800 nodes")
    circular = _fit_local_grid(exposures["1"], exposures["2"], d_grid, "circular")
    static = _fit_local_grid(exposures["1"], exposures["2"], d_grid, "static")
    combinations = []
    for (ia, ib), d_circ in circular.items():
        combinations.append({
            "epoch_a_obs_id": exposures["1"][ia]["obs_id"],
            "epoch_a_detector": exposures["1"][ia]["detector"],
            "epoch_b_obs_id": exposures["2"][ib]["obs_id"],
            "epoch_b_detector": exposures["2"][ib]["detector"],
            "d_fit_circular_au": d_circ,
            "d_fit_static_au": static[(ia, ib)],
        })
    offsets = [float(row["offset_arcsec"])
               for window_rows in exposures.values() for row in window_rows]
    step_near_median = float(np.interp(np.median(d_grid), d_grid,
                                       np.r_[np.diff(d_grid), np.diff(d_grid)[-1]]))
    result = {
        "body": body, "epoch_a": "1", "epoch_b": "2", "truth_r_au": truth,
        "truth_source": truth_source,
        "metadata_csv": str(metadata.resolve().relative_to(ROOT)),
        "n_input_rows": len(rows), "n_usable_epoch_a": len(exposures["1"]),
        "n_usable_epoch_b": len(exposures["2"]), "n_skipped": len(skipped),
        "skipped": skipped, "measurement_errors": errors,
        "fit_grid": {"kind": "geomspace", "n": len(d_grid), "min_au": 15.0,
                     "max_au": 1000.0, "step_near_median_au": step_near_median},
        "per_exposure_offset_arcsec": {"rms": float(np.sqrt(np.mean(np.square(offsets)))),
                                        "max": float(np.max(offsets))},
        "exposures": exposures, "n_combinations": len(combinations),
        "combinations": combinations,
        "circular": _stats([pair["d_fit_circular_au"] for pair in combinations], truth),
        "static": _stats([pair["d_fit_static_au"] for pair in combinations], truth),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    json_path = OUT / f"astrometric_distance_{body}_full.json"
    png_path = OUT / f"astrometric_hist_{body}_full.png"
    if json_path.exists() or png_path.exists():
        raise FileExistsError(f"Refusing to overwrite full-run output: {json_path} or {png_path}")
    json_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    fig, ax = plt.subplots(figsize=(10, 6), facecolor="white")
    ax.hist([pair["d_fit_circular_au"] for pair in combinations], bins=40,
            alpha=.7, label="Circular orbit", color="#087e8b")
    ax.hist([pair["d_fit_static_au"] for pair in combinations], bins=40,
            alpha=.55, label="Parallax only", color="#d1495b")
    ax.axvline(truth, color="#222", ls="--", lw=2, label=f"{body.title()} truth {truth:.2f} AU")
    ax.set_xlabel("Fitted heliocentric distance (AU)")
    ax.set_ylabel("Exposure combinations")
    ax.set_title(f"{body.title()} full-set astrometric distance")
    ax.grid(axis="y", alpha=.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(png_path, dpi=170, facecolor="white")
    plt.close(fig)
    print("FULL RUN", json.dumps({"body": body, "n_epoch_a": len(exposures["1"]),
          "n_epoch_b": len(exposures["2"]), "n_pairs": len(combinations),
          "truth_au": truth, "circular": result["circular"], "static": result["static"],
          "measurement_errors": len(errors), "outputs": [str(json_path), str(png_path)]}))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--body", choices=("neptune", "uranus"), required=True)
    parser.add_argument("--data-root", type=Path)
    args = parser.parse_args()
    default = ROOT if args.body == "neptune" else ROOT / "_incoming" / "uranus"
    run_full(args.body, args.data_root or default)


if __name__ == "__main__":
    main()
