"""Offline Neptune dial packaging from local December and June cutouts."""
from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS
from numpy.lib.stride_tricks import sliding_window_view

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "poc"))

from spx.geometry import predict_radec
from spx.frame import bad_mask, wavelength_at

def _science_scorer():
    """Load the unchanged PoC B scorer without importing its network workflow."""
    path = ROOT / "poc" / "poc_b_dial_v2.py"
    tree = ast.parse(path.read_text())
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "_variance_snr")
    namespace = {"np": np, "sliding_window_view": sliding_window_view}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["_variance_snr"]


_variance_snr = _science_scorer()


def _rows(path: Path) -> list[dict]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def _reference(rows: list[dict], pass_a: int) -> dict:
    valid = [r for r in rows if int(r["window_id"]) == pass_a and r["status"] == "ok"
             and Path(r["local_path"]).is_file()]
    if not valid:
        raise ValueError(f"pass A {pass_a} has no local cutouts")
    return min(valid, key=lambda r: (float(r["bad_frac"]), float(r["mjd"]), r["obs_id"]))


def _candidates(paths: list[Path], pass_window: dict) -> list[dict]:
    candidates = []
    for path in sorted(paths):
        with fits.open(path, memmap=False) as hdul:
            header = hdul["IMAGE"].header
            mjd = float(header["MJD-OBS"])
            if pass_window["mjd_min"] is not None and mjd < pass_window["mjd_min"] - 15:
                continue
            if pass_window["mjd_max"] is not None and mjd > pass_window["mjd_max"] + 15:
                continue
            candidates.append({"path": path, "mjd": mjd, "detector": int(header["DETECTOR"]),
                               "wcs": WCS(header), "shape": hdul["IMAGE"].data.shape})
    return candidates


def _inside(candidate: dict, ra_deg: float, dec_deg: float, margin_px: float = 20) -> bool:
    x, y = candidate["wcs"].world_to_pixel_values(ra_deg, dec_deg)
    height, width = candidate["shape"]
    return bool(np.isfinite(x) and np.isfinite(y) and margin_px <= x < width - margin_px
                and margin_px <= y < height - margin_px)


def _source_url(path: Path) -> str:
    name = path.name.split("__c", 1)[0]
    match = re.fullmatch(r"level2_(\d{4}W\d{2}_[12][AB])_\d+_([1-4])D[1-6]_spx_(l2b-v\d+-\d+-\d+)\.fits", name)
    if not match:
        raise ValueError(f"cannot reconstruct IRSA source URL for {path}")
    week, channel, version = match.groups()
    return f"https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/level2/{week}/{version}/{channel}/{name}"


def _choose(distance_au: float, reference: dict, t0: Time, candidates: list[dict]) -> tuple[dict, dict] | None:
    viable = []
    ra0, dec0 = float(reference["eph_ra"]), float(reference["eph_dec"])
    for item in candidates:
        if item["detector"] != int(reference["detector"]):
            continue
        pred = predict_radec(ra0, dec0, t0, distance_au,
                             Time(item["mjd"], format="mjd", scale="utc"))[0]
        if not _inside(item, float(pred[0]), float(pred[1])):
            continue
        with fits.open(item["path"], memmap=False) as hdul:
            wave_um, _, _, _ = wavelength_at(hdul, float(pred[0]), float(pred[1]))
        if np.isfinite(wave_um):
            viable.append((abs(wave_um - float(reference["wavelength_um"])),
                           item["mjd"], str(item["path"]), item,
                           {"ra_deg": float(pred[0]), "dec_deg": float(pred[1])}))
    if not viable:
        return None
    _, _, _, item, pred = min(viable, key=lambda row: row[:3])
    return item, pred


def _score(item: dict, pred: dict, radius_px: float) -> tuple[float, float] | None:
    with fits.open(item["path"], memmap=False) as hdul:
        image = np.asarray(hdul["IMAGE"].data, dtype=float)
        image -= np.asarray(hdul["ZODI"].data, dtype=float)
        variance = np.asarray(hdul["VARIANCE"].data, dtype=float)
        bad = bad_mask(hdul["FLAGS"].data, hdul["FLAGS"].header)
        image[bad] = np.nan
        variance[bad] = np.nan
        x, y = item["wcs"].world_to_pixel_values(pred["ra_deg"], pred["dec_deg"])
        ix, iy = int(round(x)), int(round(y))
        half = 32
        image = image[iy-half:iy+half, ix-half:ix+half]
        variance = variance[iy-half:iy+half, ix-half:ix+half]
    if image.shape != (64, 64):
        return None
    snr, offset = _variance_snr(image, variance, np.zeros_like(variance), 0.0,
                                 search_radius=radius_px)
    return (snr, offset) if snr is not None else None


def build_dial(field_id: str, target: str, pass_a: int, pass_b: int,
               n_steps: int, dmin_au: float, dmax_au: float,
               search_radius_px: float = 20) -> dict:
    if target != "neptune":
        raise ValueError("only local Neptune data are supported")
    base = ROOT / "data" / "meta" / target
    windows = {int(p["window_id"]): p for p in json.loads((base / "passes.json").read_text())["passes"]}
    reference = _reference(_rows(base / "epochs.csv"), pass_a)
    truth_row = min((r for r in _rows(base / "raw_index.csv")
                     if r["collection"] == "spherex_dr1" and int(r["detector"]) == int(reference["detector"])),
                    key=lambda r: abs(float(r["mjd"]) - float(reference["mjd"])))
    truth_au = float(truth_row["r_au"])
    t0 = Time(float(reference["mjd"]), format="mjd", scale="utc")
    candidates = _candidates(list((ROOT / "data" / "raw" / target).glob("*.fits"))
                             + list((base / "templates").glob("*.fits")), windows[pass_b])
    candidates = [c for c in candidates if c["detector"] == int(reference["detector"])
                  and c["mjd"] > windows[pass_a]["mjd_max"] + 45]
    skipped = []
    steps = []

    def scan(grid: np.ndarray) -> None:
        for distance in grid:
            d = float(distance)
            if any(abs(s["distance_au"] - d) < 1e-9 for s in steps):
                continue
            chosen = _choose(d, reference, t0, candidates)
            if chosen is None:
                skipped.append({"distance_au": d, "reason": "no_local_pass_b_coverage"})
                continue
            item, pred = chosen
            score = _score(item, pred, search_radius_px)
            if score is None:
                skipped.append({"distance_au": d, "reason": "no_valid_snr"})
                continue
            steps.append({"distance_au": d, "path": str(item["path"]), "mjd": item["mjd"],
                          "pred": pred, "snr": score[0], "offset_px": score[1]})

    scan(np.geomspace(dmin_au, dmax_au, n_steps))
    coarse_peak = max(steps, key=lambda row: row["snr"])["distance_au"] if steps else None
    if coarse_peak is not None:
        scan(np.geomspace(max(dmin_au, 0.8 * coarse_peak), min(dmax_au, 1.25 * coarse_peak), 12))
    steps.sort(key=lambda row: row["distance_au"])
    peak = max(steps, key=lambda row: row["snr"]) if steps else None
    error_pct = 100 * abs(peak["distance_au"] / truth_au - 1) if peak else None
    result = {"field_id": field_id, "target": target, "reference_path": reference["local_path"],
              "reference_obs_id": reference["obs_id"], "reference_mjd": float(reference["mjd"]),
              "reference_detector": int(reference["detector"]), "truth_r_au": truth_au,
              "truth_delta_au": float(truth_row["delta_au"]), "truth_source": truth_row["eph_source"],
              "peak_distance_au": peak["distance_au"] if peak else None,
              "error_pct": error_pct, "peak_over_median_snr": (peak["snr"] / float(np.median([s["snr"] for s in steps]))) if peak and np.median([s["snr"] for s in steps]) else None,
              "available_pass_b_cutouts": len(candidates), "steps": steps, "skipped": skipped,
              "published": False,
              "publication_reason": "peak error exceeds 20%" if peak and error_pct > 20 else
                                    "no valid covered steps" if not peak else
                                    "packaging requires matched-sky science review and verified download timestamps"}
    (base / "dial_summary.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--pass-a", type=int, required=True)
    parser.add_argument("--pass-b", type=int, required=True)
    parser.add_argument("--steps", type=int, default=48)
    parser.add_argument("--dmin", type=float, default=15)
    parser.add_argument("--dmax", type=float, default=1000)
    args = parser.parse_args()
    result = build_dial(args.id, args.target, args.pass_a, args.pass_b,
                        args.steps, args.dmin, args.dmax)
    print(f"peak={result['peak_distance_au']} AU, truth={result['truth_r_au']:.3f} AU, "
          f"error={result['error_pct']}%, no coverage={sum(s['reason'] == 'no_local_pass_b_coverage' for s in result['skipped'])}")
    print(result["publication_reason"])


if __name__ == "__main__":
    main()
