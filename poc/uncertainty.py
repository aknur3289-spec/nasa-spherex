"""Bootstrap and centroid-offset uncertainty summaries for existing astrometry fits."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from astropy.time import Time

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "pipeline"))
from spx.geometry import ang_sep_deg, predict_radec

PIXEL_ARCSEC = 6.15
BOOTSTRAP_RESAMPLES = 10_000
SEED = 20261114
RUNS = {
    "neptune_all": "astrometric_distance_all.json",
    "uranus": "astrometric_distance_uranus.json",
    "neptune_w23": "astrometric_distance_neptune_w23.json",
}


def _epoch_map(run: dict) -> dict[str, dict[str, dict]]:
    return {epoch: {row["obs_id"]: row for row in exposures}
            for epoch, exposures in run["exposures"].items()}


def _offsets(run: dict) -> np.ndarray:
    return np.asarray([float(row["offset_arcsec"])
                       for exposures in run["exposures"].values()
                       for row in exposures], dtype=float)


def _sensitivity(run: dict, epochs: dict, distance_key: str, h: float = 0.01) -> float:
    """Median absolute finite-difference derivative of angular miss (arcsec/AU)."""
    a_epoch = str(run.get("epoch_a", sorted(epochs, key=int)[0]))
    b_epoch = str(run.get("epoch_b", sorted(epochs, key=int)[1]))
    vals = []
    for pair in run["combinations"]:
        a = epochs[a_epoch][pair["epoch_a_obs_id"]]
        b = epochs[b_epoch][pair["epoch_b_obs_id"]]
        d = float(pair[distance_key])
        t0 = Time(float(a["mjd"]), format="mjd", scale="utc")
        t1 = Time(float(b["mjd"]), format="mjd", scale="utc")
        misses = []
        for trial_d in (d-h, d+h):
            predicted = predict_radec(a["measured_ra_deg"], a["measured_dec_deg"],
                                      t0, trial_d, t1, orbit="circular")[0]
            misses.append(float(ang_sep_deg(predicted[0], predicted[1],
                                            b["measured_ra_deg"], b["measured_dec_deg"]))*3600)
        deriv = abs((misses[1]-misses[0])/(2*h))
        if np.isfinite(deriv) and deriv > 0:
            vals.append(deriv)
    if not vals:
        raise RuntimeError(f"No finite positive miss sensitivity for {run['body']}")
    return float(np.median(vals))


def summarize(name: str, path: Path, rng: np.random.Generator) -> dict:
    run = json.loads(path.read_text())
    epochs = _epoch_map(run)
    dvals = np.asarray([p["d_fit_circular_au"] for p in run["combinations"]], dtype=float)
    boot = np.empty(BOOTSTRAP_RESAMPLES, dtype=float)
    for i in range(BOOTSTRAP_RESAMPLES):
        boot[i] = np.median(rng.choice(dvals, size=len(dvals), replace=True))
    q16, q84 = np.percentile(boot, [16, 84])
    offsets = _offsets(run)
    offset_rms = float(np.sqrt(np.mean(offsets**2)))
    sensitivity = _sensitivity(run, epochs, "d_fit_circular_au")
    return {
        "source_json": str(path.relative_to(ROOT)),
        "body": run["body"],
        "n_pairs": len(dvals),
        "median_d_au": float(np.median(dvals)),
        "truth_r_au": float(run["truth_r_au"]),
        "bootstrap": {
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": SEED,
            "ci_level": 0.68,
            "median_ci_au": [float(q16), float(q84)],
            "plus_minus_au": float((q84-q16)/2),
            "method": "percentile interval of bootstrap medians, resampling fitted exposure-pair distances",
        },
        "centroid_offset_arcsec": {
            "min": float(np.min(offsets)), "median": float(np.median(offsets)),
            "max": float(np.max(offsets)), "rms": offset_rms,
            "rms_px": offset_rms/PIXEL_ARCSEC,
            "max_px": float(np.max(offsets))/PIXEL_ARCSEC,
        },
        "local_sensitivity_arcsec_per_au": sensitivity,
        "centroid_propagated_sigma_d_au": offset_rms/sensitivity,
        "max_offset_distance_bound_au": float(np.max(offsets))/sensitivity,
        "propagation_note": "Uses RMS (or maximum) measured-vs-ephemeris centroid offset divided by median absolute finite-difference derivative of target-position angular miss at each pair's fitted distance (central difference, ±0.01 AU). This is a scale estimate, not a full covariance model.",
    }


def main() -> None:
    rng = np.random.default_rng(SEED)
    results = {name: summarize(name, ROOT/"poc"/"out"/filename, rng)
               for name, filename in RUNS.items()}
    output = {"bootstrap_resamples": BOOTSTRAP_RESAMPLES, "results": results}
    out_path = ROOT/"poc"/"out"/"uncertainty.json"
    out_path.write_text(json.dumps(output, indent=2, allow_nan=False)+"\n")
    for name, result in results.items():
        print(name, json.dumps({"median_d_au": result["median_d_au"],
                                "bootstrap_ci_au": result["bootstrap"]["median_ci_au"],
                                "bootstrap_pm_au": result["bootstrap"]["plus_minus_au"],
                                "offset_arcsec": result["centroid_offset_arcsec"],
                                "sensitivity_arcsec_per_au": result["local_sensitivity_arcsec_per_au"],
                                "centroid_sigma_d_au": result["centroid_propagated_sigma_d_au"],
                                "max_offset_bound_au": result["max_offset_distance_bound_au"]}))


if __name__ == "__main__":
    main()
