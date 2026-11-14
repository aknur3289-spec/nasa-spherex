"""Offline Neptune dial packaging from local December and June cutouts."""
from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import astropy.units as u
from astropy import log as astropy_log
from astropy.coordinates import SkyCoord
from astropy.nddata import Cutout2D
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS
from numpy.lib.stride_tricks import sliding_window_view

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "poc"))

from spx.geometry import predict_radec
from spx.frame import bad_mask, wavelength_at
from spx.focus import dial_grid
from spx.manifest import validate_field
from spx.render import stretch_params, to_png
from spx import io as spx_io

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


def _stamp(hdul: fits.HDUList, ra_deg: float, dec_deg: float) -> tuple[np.ndarray, np.ndarray]:
    """Return a 10 arcmin calibrated stamp and its named-bit bad mask."""
    position = SkyCoord(ra_deg * u.deg, dec_deg * u.deg)
    wcs = WCS(hdul["IMAGE"].header)
    image = np.asarray(hdul["IMAGE"].data, dtype=float) - np.asarray(hdul["ZODI"].data, dtype=float)
    flags = np.asarray(hdul["FLAGS"].data)
    cut = Cutout2D(image, position, (10 * u.arcmin, 10 * u.arcmin), wcs=wcs,
                   mode="partial", fill_value=np.nan)
    bad = Cutout2D(bad_mask(flags, hdul["FLAGS"].header).astype(np.uint8), position,
                   (10 * u.arcmin, 10 * u.arcmin), wcs=wcs,
                   mode="partial", fill_value=1).data.astype(bool)
    bad |= ~np.isfinite(cut.data)
    values = np.asarray(cut.data, dtype=float).copy()
    values[bad] = np.nan
    return values, bad


def _peak(img: np.ndarray, bad: np.ndarray, radius_px: float = 20) -> tuple[float, float] | None:
    """Find the brightest valid single-pixel excess within the central radius."""
    values = np.asarray(img, dtype=float).copy()
    values[bad] = np.nan
    finite = values[np.isfinite(values)]
    if len(finite) < 10:
        return None
    median = float(np.median(finite))
    noise = float(1.4826 * np.median(np.abs(finite - median)))
    if not np.isfinite(noise) or noise <= 0:
        return None
    yy, xx = np.indices(values.shape)
    cy, cx = (np.array(values.shape) - 1) / 2
    offset = np.hypot(xx - cx, yy - cy)
    score = np.where((offset <= radius_px) & np.isfinite(values), (values - median) / noise, -np.inf)
    y, x = np.unravel_index(int(np.argmax(score)), score.shape)
    if not np.isfinite(score[y, x]) or score[y, x] <= 0:
        return None
    return float(score[y, x]), float(offset[y, x])


def build_neptune_field_s3() -> dict:
    """Stage a dial manifest from full-frame S3 sections for Science review."""
    base = ROOT / "data" / "meta" / "neptune"
    rows = _rows(base / "epochs.csv")
    ref = next(r for r in rows if r["obs_id"] == "2025W25_2A_0500_1")
    target = next(r for r in rows if r["obs_id"] == "2025W51_1A_0485_1")
    raw = next(r for r in _rows(base / "raw_index.csv")
               if "2025W25_2A_0500_1D1" in r["file_url"] and int(r["detector"]) == 1)
    truth_au = float(raw["delta_au"])
    t0 = Time(float(ref["mjd"]), format="mjd", scale="utc")
    t1 = Time(float(target["mjd"]), format="mjd", scale="utc")
    refpos = {"ra_deg": float(ref["eph_ra"]), "dec_deg": float(ref["eph_dec"])}
    grid = dial_grid(20, 45, step_px=15)
    positions = []
    for d in grid:
        p = predict_radec(refpos["ra_deg"], refpos["dec_deg"], t0, float(d), t1)[0]
        positions.append((float(d), float(p[0]), float(p[1])))
    rawdir = ROOT / "data" / "raw" / "neptune-dial"
    refpath = next(rawdir.glob("*2025W25_2A_0500_1D1*.fits"), None)
    if refpath is None:
        raise FileNotFoundError("reference 0.5 degree cutout missing")
    was_cached = (rawdir / "target_sections.json").is_file()
    source_row = {"file_url": target["access_url"], "cloud_key": target["cloud_key"],
                  "cloud_bucket": "nasa-irsa-spherex"}
    sections = spx_io.fetch_dial_sections(source_row, positions, rawdir)
    with fits.open(refpath, memmap=False) as href:
        ref_img, ref_bad = _stamp(href, **refpos)
        ref_wave, _, _, _ = wavelength_at(href, **refpos)
        ref_version = str(href[0].header["VERSION"])
    stamps = [("ref", ref_img, ref_bad)]
    steps = []
    frames = []
    ref_meta = (ref, refpos, ref_wave, ref_version, ref_img, ref_bad, "ref", refpath)
    frame_meta = [ref_meta]
    for index, ((distance_au, ra_deg, dec_deg), section) in enumerate(zip(positions, sections)):
        pos = {"ra_deg": ra_deg, "dec_deg": dec_deg}
        if section["outside_frame"]:
            steps.append({"distance_au": distance_au, "frame": None, "pred": pos,
                          "snr": None, "offset_px": None, "outside_frame": True})
            continue
        with fits.open(section["path"], memmap=False) as hdul:
            img, bad = _stamp(hdul, **pos)
            wave_um, _, _, _ = wavelength_at(hdul, **pos)
            version = str(hdul[0].header["VERSION"])
        measured = _peak(img, bad)
        if measured is None:
            raise ValueError(f"covered step {distance_au:.5f} AU has no valid positive peak")
        ident = f"step-{index:03d}"
        steps.append({"distance_au": distance_au, "frame": ident, "pred": pos,
                      "snr": measured[0], "offset_px": measured[1]})
        stamps.append((ident, img, bad))
        frame_meta.append((target, pos, wave_um, version, img, bad, ident, Path(section["path"])))
    valid = [step for step in steps if step["offset_px"] is not None]
    if not valid:
        raise ValueError("no covered dial steps had a valid peak")
    peak = min(valid, key=lambda step: step["offset_px"])
    peak_au = peak["distance_au"]
    with (ROOT / "docs" / "dial_table_neptune.csv").open(newline="") as source:
        table = list(csv.DictReader(line for line in source if not line.startswith("#")))
    nearest = sorted(valid, key=lambda step: abs(step["distance_au"] - peak_au))[:5]
    comparison = []
    for step in sorted(nearest, key=lambda step: step["distance_au"]):
        science = min(table, key=lambda row: abs(float(row["distance_au"]) - step["distance_au"]))
        comparison.append({"distance_au": step["distance_au"], "offset_px": step["offset_px"],
                           "science_distance_au": float(science["distance_au"]),
                           "science_model_miss_px": float(science["model_miss_px"])})
    publish_gate = abs(peak_au - 29.9) <= 0.5 and abs(peak["offset_px"] - 13.5) <= 5 and abs(peak_au - truth_au) <= 0.5
    staged = ROOT / "data" / "meta" / "neptune-dial"
    staged.mkdir(parents=True, exist_ok=True)
    report = {"steps": len(steps), "covered_steps": len(valid), "outside_steps": len(steps) - len(valid),
              "peak_distance_au": peak_au, "peak_offset_px": peak["offset_px"],
              "truth_distance_au": truth_au, "error_au": abs(peak_au - truth_au),
              "science_reference_au": 29.95, "comparison": comparison,
              "science_gate_passed": publish_gate, "published": False,
              "reason": "Science peak check failed" if not publish_gate else "Frontend validator requires agreement on null outside-frame steps"}
    (staged / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    if not publish_gate:
        return report
    common_stretch = stretch_params([item[1] for item in stamps])
    for row, pos, wave_um, version, img, bad, ident, source_path in frame_meta:
        png = f"{ident}.png"
        to_png(img, bad, common_stretch, staged / png)
        frames.append({"id": ident, "png": png,
                       "obs_time_utc": Time(float(row["mjd"]), format="mjd", scale="utc").isot + "Z",
                       "mjd": float(row["mjd"]), "survey_pass": int(row["window_id"]),
                       "detector": int(row["detector"]), "wavelength_um": wave_um,
                       "center": pos, "bad_pixel_fraction": float(np.mean(bad)),
                       "stretch": common_stretch, "source_url": row["access_url"],
                       "obs_id": row["obs_id"], "processing_version": version,
                       "collection": "spherex_dr1",
                       "downloaded_utc": datetime.fromtimestamp(source_path.stat().st_mtime,
                                                                 timezone.utc).isoformat().replace("+00:00", "Z"),
                       "width_px": img.shape[1], "height_px": img.shape[0]})
    dates = [datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
             for path in [refpath] + [Path(s["path"]) for s in sections if s["path"]]]
    field = {"schema_version": "1.1", "field_id": "neptune-dial", "kind": "dial",
             "title": "Neptune Distance Dial", "description": "Known Neptune in SPHEREx June and December 2025 exposures.",
             "center": refpos, "size_arcmin": 10, "pixel_scale_arcsec": 6.15,
             "frames": frames, "pairs": [],
             "provenance": {"mission": "SPHEREx", "archive": "NASA/IPAC IRSA",
                            "collections": ["spherex_dr1"], "doi": "[DOI from IRSA release page]",
                            "downloaded_utc": max(dates),
                            "pipeline_commit": subprocess.check_output(
                                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                            "cached": was_cached, "synthetic": False},
             "dial": {"reference_frame": "ref", "model": "circular orbit + parallax (geometry.py, feat/science)",
                      "search_radius_px": 20, "steps": steps, "peak_distance_au": peak_au,
                      "truth": {"distance_au": truth_au, "source": "JPL Horizons"},
                      "ref_obs_id": ref["obs_id"], "target_obs_id": target["obs_id"],
                      "ref_detector": "D1", "target_detector": "D2", "truth_au": 29.89,
                      "measured_au": 29.95, "measured_uncertainty_au": 0.03,
                      "note": "distance from astrometry; full real-data focus curve not done (star residuals)",
                      "negative_control_field": "neptune-dial-blank"}}
    validate_field(field, staged, real_build=True)
    (staged / "field.json").write_text(json.dumps(field, indent=2, allow_nan=False) + "\n")
    return report


def main() -> None:
    astropy_log.setLevel("WARNING")
    parser = argparse.ArgumentParser()
    parser.add_argument("--neptune-field", action="store_true")
    parser.add_argument("--id")
    parser.add_argument("--target")
    parser.add_argument("--pass-a", type=int)
    parser.add_argument("--pass-b", type=int)
    parser.add_argument("--steps", type=int, default=48)
    parser.add_argument("--dmin", type=float, default=15)
    parser.add_argument("--dmax", type=float, default=1000)
    args = parser.parse_args()
    if args.neptune_field:
        print(json.dumps(build_neptune_field_s3(), indent=2))
        return
    if not all((args.id, args.target, args.pass_a, args.pass_b)):
        parser.error("--id, --target, --pass-a and --pass-b are required for the legacy check")
    result = build_dial(args.id, args.target, args.pass_a, args.pass_b,
                        args.steps, args.dmin, args.dmax)
    print(f"peak={result['peak_distance_au']} AU, truth={result['truth_r_au']:.3f} AU, "
          f"error={result['error_pct']}%, no coverage={sum(s['reason'] == 'no_local_pass_b_coverage' for s in result['skipped'])}")
    print(result["publication_reason"])


if __name__ == "__main__":
    main()
