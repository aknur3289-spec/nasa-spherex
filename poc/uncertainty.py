"""Refine astrometric pair distances and estimate bootstrap/position uncertainties."""
from __future__ import annotations

import json
import math
import argparse
import sys
from pathlib import Path

import numpy as np
from astropy.time import Time
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from spx.geometry import ang_sep_deg, predict_radec

PIXEL_ARCSEC = 6.15
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 42
RUNS = {
    "neptune_all": ("astrometric_distance_all.json", 200.0, 1500.0),
    "uranus": ("astrometric_distance_uranus.json", 400.0, 3000.0),
    "neptune_w23": ("astrometric_distance_neptune_w23.json", 200.0, 1500.0),
}


def miss_arcsec(d, ra0, dec0, t0, ra1, dec1, t1):
    # predict_radec in this repository accepts an astropy Time (scalar is promoted to 1-D).
    predicted = predict_radec(ra0, dec0, t0, d, t1, orbit="circular")
    return float(ang_sep_deg(predicted[0, 0], predicted[0, 1], ra1, dec1) * 3600)


def refine(d_grid, *p):
    result = minimize_scalar(miss_arcsec, bounds=(d_grid - 0.3, d_grid + 0.3), args=p,
                             method="bounded", options={"xatol": 1e-4})
    return float(result.x), float(result.fun)


def sensitivity_arcsec_per_au(d, ra0, dec0, t0, t1, h=0.01):
    predicted_plus = predict_radec(ra0, dec0, t0, d + h, t1, orbit="circular")
    predicted_minus = predict_radec(ra0, dec0, t0, d - h, t1, orbit="circular")
    return float(ang_sep_deg(predicted_plus[0, 0], predicted_plus[0, 1],
                             predicted_minus[0, 0], predicted_minus[0, 1]) * 3600 / (2 * h))


def _epoch_rows(run):
    return {str(epoch): {row["obs_id"]: row for row in rows}
            for epoch, rows in run["exposures"].items()}


def _grid_step(run, at_distance):
    # The astrometry workflow's fit_distance grid is geomspace(15, 1000, 1800).
    # Use the local adjacent spacing at the refined median.
    grid = np.geomspace(15.0, 1000.0, 1800)
    idx = int(np.searchsorted(grid, at_distance))
    if idx <= 0:
        return float(grid[1] - grid[0])
    if idx >= len(grid):
        return float(grid[-1] - grid[-2])
    return float(grid[idx] - grid[idx - 1])


def load_pair_inputs(run):
    """Use the exact measured exposure rows serialized by poc_b_astrometry.py."""
    epochs = _epoch_rows(run)
    epoch_names = sorted(epochs, key=int)
    epoch_a = str(run.get("epoch_a", epoch_names[0]))
    epoch_b = str(run.get("epoch_b", epoch_names[1]))
    pairs = []
    for pair in run["combinations"]:
        a = epochs[epoch_a][pair["epoch_a_obs_id"]]
        b = epochs[epoch_b][pair["epoch_b_obs_id"]]
        pairs.append({
            "epoch_a_obs_id": pair["epoch_a_obs_id"],
            "epoch_b_obs_id": pair["epoch_b_obs_id"],
            "ra0": float(a["measured_ra_deg"]),
            "dec0": float(a["measured_dec_deg"]),
            "t0": Time(float(a["mjd"]), format="mjd", scale="utc"),
            "ra1": float(b["measured_ra_deg"]),
            "dec1": float(b["measured_dec_deg"]),
            "t1": Time(float(b["mjd"]), format="mjd", scale="utc"),
            "seed_d": float(pair["d_fit_circular_au"]),
        })
    return pairs


def summarize(name, filename, s_min, s_max, rng):
    path = ROOT / "poc" / "out" / filename
    run = json.loads(path.read_text())
    pairs = load_pair_inputs(run)
    refined = []
    sensitivities = []
    pair_results = []
    for pair in pairs:
        args = (pair["ra0"], pair["dec0"], pair["t0"], pair["ra1"], pair["dec1"], pair["t1"])
        d_refined, residual = refine(pair["seed_d"], *args)
        sensitivity = sensitivity_arcsec_per_au(d_refined, pair["ra0"], pair["dec0"], pair["t0"], pair["t1"])
        refined.append(d_refined)
        sensitivities.append(sensitivity)
        pair_results.append({"epoch_a_obs_id": pair["epoch_a_obs_id"],
                             "epoch_b_obs_id": pair["epoch_b_obs_id"],
                             "d_refined_au": d_refined,
                             "residual_arcsec": residual,
                             "sensitivity_arcsec_per_au": sensitivity})
    dvals = np.asarray(refined, dtype=float)
    median = float(np.median(dvals))
    p16, p84 = (float(x) for x in np.percentile(dvals, [16, 84]))
    boot_medians = np.empty(BOOTSTRAP_RESAMPLES, dtype=float)
    for i in range(BOOTSTRAP_RESAMPLES):
        boot_medians[i] = float(np.median(rng.choice(dvals, size=len(dvals), replace=True)))
    boot16, boot84 = (float(x) for x in np.percentile(boot_medians, [16, 84]))
    offsets = np.asarray([float(row["offset_arcsec"])
                          for rows in run["exposures"].values() for row in rows], dtype=float)
    offset_rms = float(np.sqrt(np.mean(offsets**2)))
    offset_max = float(np.max(offsets))
    sensitivity = float(np.median(sensitivities))
    truth = float(run["truth_r_au"])
    return {
        "run": name,
        "source_json": str(path.relative_to(ROOT)),
        "truth_au": truth,
        "headline_median_au": float(run["circular"]["median_d_fit_au"]),
        "n_pairs": len(dvals),
        "refined_median_au": median,
        "p16_au": p16,
        "p84_au": p84,
        "bootstrap_ci_68_au": [boot16, boot84],
        "bootstrap_half_width_au": (boot84 - boot16) / 2,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "sensitivity_arcsec_per_au": sensitivity,
        "sensitivity_min_required": s_min,
        "sensitivity_max_required": s_max,
        "offset_rms_arcsec": offset_rms,
        "offset_max_arcsec": offset_max,
        "sigma_centroid_au": offset_rms / sensitivity,
        "bound_max_au": offset_max / sensitivity,
        "grid_step_au": _grid_step(run, median),
        "pairs": pair_results,
        "checks": {
            "sensitivity": s_min < sensitivity < s_max,
            "sigma_centroid": offset_rms / sensitivity < 0.1,
            "bound_max": offset_max / sensitivity < 0.2,
            "median_matches_headline": abs(median - float(run["circular"]["median_d_fit_au"])) < 0.05,
            "truth_error_below_1pct": abs(median-truth)/truth < 0.01,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-body", choices=("neptune", "uranus"))
    args = parser.parse_args()
    if args.full_body:
        name = f"{args.full_body}_full"
        filename = f"astrometric_distance_{args.full_body}_full.json"
        output_path = ROOT / "poc" / "out" / f"uncertainty_{args.full_body}_full.json"
        if output_path.exists():
            raise FileExistsError(f"Refusing to overwrite {output_path}")
        s_min, s_max = (200.0, 1500.0) if args.full_body == "neptune" else (400.0, 3000.0)
        results = {name: summarize(name, filename, s_min, s_max,
                                   np.random.default_rng(BOOTSTRAP_SEED))}
    else:
        output_path = ROOT / "poc" / "out" / "uncertainty.json"
        results = {name: summarize(name, *spec, np.random.default_rng(BOOTSTRAP_SEED))
                   for name, spec in RUNS.items()}
    failed = [(name, check) for name, result in results.items()
              for check, passed in result["checks"].items() if not passed]
    for name, result in results.items():
        try:
            assert result["sensitivity_min_required"] < result["sensitivity_arcsec_per_au"] < result["sensitivity_max_required"]
            assert result["sigma_centroid_au"] < 0.1
            assert result["bound_max_au"] < 0.2
            assert abs(result["refined_median_au"]-result["headline_median_au"]) < 0.05
            assert abs(result["refined_median_au"]-result["truth_au"])/result["truth_au"] < 0.01
        except AssertionError:
            if (name, "assertion") not in failed:
                failed.append((name, "assertion"))
    if failed:
        print("SANITY CHECKS FAILED; no output JSON written and no documentation should be changed.")
        for name, result in results.items():
            print(name, json.dumps({k: v for k, v in result.items() if k != "pairs"}, sort_keys=True))
            print(name, "failed_checks", [check for check, passed in result["checks"].items() if not passed])
        return 2
    headline = results.get("neptune_all", next(iter(results.values())))
    half_width = headline["bootstrap_half_width_au"]
    uncertainty = max(half_width, headline["sigma_centroid_au"])
    U = max(0.01, math.ceil(uncertainty * 100 - 1e-12) / 100)
    output = {"bootstrap_resamples": BOOTSTRAP_RESAMPLES,
              "bootstrap_seed": BOOTSTRAP_SEED,
              "headline_uncertainty_U_au": U,
              "headline_uncertainty_rule": "ceil(max(bootstrap CI half-width, centroid sigma) to 0.01 AU; minimum 0.01 AU)",
              "runs": results}
    output_path.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    print("SANITY CHECKS PASSED")
    for name, result in results.items():
        print(name, json.dumps({k: v for k, v in result.items() if k != "pairs"}, sort_keys=True))
    print("U_au", f"{U:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
