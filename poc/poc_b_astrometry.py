#!/usr/bin/env python
"""PoC B-lite: measure Neptune astrometry in real SPHEREx exposure sections."""
from __future__ import annotations

import csv
import json
import math
import re
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.time import Time
import astropy.units as u

from spx.geometry import ang_sep_deg, fit_distance, predict_radec
from spx.horizons import ephem
from realdata import RAW, read_section, sia_frames, find_cached_section
from poc_b_dial import _inside_region

ROOT = Path(__file__).resolve().parents[1]
POC = Path(__file__).resolve().parent
OUT = POC / "out"
PIXEL_ARCSEC = 6.15
START = time.monotonic()
TIME_LIMIT = 30 * 60


def _check_time():
    if time.monotonic() - START > TIME_LIMIT:
        raise TimeoutError("PoC B-lite exceeded its 30-minute time box")


def _detector(row):
    m = re.search(r"D([1-3])_spx_", row["access_url"])
    return int(m.group(1)) if m else None


def _exposures_for_epoch(window_id):
    with (POC / "windows_neptune.csv").open(newline="") as f:
        window = next(r for r in csv.DictReader(f) if r["window_id"] == str(window_id))
    with (POC / "coverage_neptune.csv").open(newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("window_id") == str(window_id)
                and r.get("obs_collection") == "spherex_dr1"
                and r.get("algorithm_name") == "exposure"
                and str(r.get("dataproduct_subtype", "")).lower() == "science"
                and _detector(r) is not None]
    by_mjd = {}
    for row in rows:
        by_mjd.setdefault(float(row["t_min"]), []).append(row)
    mjds = sorted(by_mjd)
    times = [Time(mjd, format="mjd", scale="utc").isot for mjd in mjds]
    eph_rows = ephem("neptune", times)
    eph_by_mjd = {round(float(e["jd_utc"] - 2400000.5), 7): e for e in eph_rows}
    accepted = []
    for mjd, time_rows in by_mjd.items():
        _check_time()
        e = min(eph_rows, key=lambda q: abs((float(q["jd_utc"] - 2400000.5) - mjd)))
        for row in time_rows:
            if _inside_region(row.get("s_region", ""), e["ra_deg"], e["dec_deg"]):
                accepted.append((row, e, mjd))
    # One detector image per observation; prefer D1, then spread the selected
    # observations across the available times in the survey pass.
    by_obs = {}
    for row, e, mjd in accepted:
        key = str(row.get("obs_id", ""))
        if key not in by_obs or _detector(row) < _detector(by_obs[key][0]):
            by_obs[key] = (row, e, mjd)
    ordered = sorted(by_obs.values(), key=lambda q: q[2])
    if len(ordered) <= 3:
        chosen = ordered
    elif len(ordered) > 0:
        indexes = sorted(set([0, (len(ordered)-1)//2, len(ordered)-1]))
        chosen = [ordered[i] for i in indexes]
    print(f"Epoch {window_id}: {len(rows)} D1-D3 frames, {len(accepted)} contain Neptune, {len(chosen)} selected")
    return window, chosen


def _stamp64(section, ra, dec):
    x, y = section["wcs"].world_to_pixel(SkyCoord(float(ra)*u.deg, float(dec)*u.deg))
    x, y = float(x), float(y)
    lx, ly = x-section["x0"], y-section["y0"]
    ix, iy = int(round(lx)), int(round(ly))
    # A 64 px cutout is approximately 0.11 deg at the SPHEREx pixel scale.
    x0, y0 = ix-32, iy-32
    planes = {}
    for name, arr in (("image", section["image"]), ("flags", section["flags"]),
                      ("variance", section.get("variance"))):
        out = np.full((64, 64), np.nan if name != "flags" else 0, dtype=float)
        if arr is not None:
            xa, xb = max(0, x0), min(arr.shape[1], x0+64)
            ya, yb = max(0, y0), min(arr.shape[0], y0+64)
            if xa < xb and ya < yb:
                out[ya-y0:yb-y0, xa-x0:xb-x0] = arr[ya:yb, xa:xb]
        planes[name] = out
    return planes, (x0+section["x0"], y0+section["y0"]), (x, y)


def _saturation_mask(flag_header, flags):
    names = {int(k[-4:]): str(v).strip().upper() for k, v in flag_header.items()
             if re.fullmatch(r"MSKN\d{4}", k)}
    mask = np.zeros(flags.shape, dtype=bool)
    for bit, name in names.items():
        if name in {"OVERFLOW", "NONLINEAR", "BLOOM"}:
            mask |= (flags.astype(np.int64) & (1 << bit)) != 0
    return mask


def _measure(row, ephrow, mjd):
    _check_time()
    rae, dece = float(ephrow["ra_deg"]), float(ephrow["dec_deg"])
    section = find_cached_section(row, [(rae, dece)])
    if section is None:
        section = read_section(row, [(rae, dece)])
    if section.get("variance") is None:
        raise RuntimeError(f"No VARIANCE section for obs_id={row.get('obs_id')}")
    stamp, origin, epix = _stamp64(section, rae, dece)
    image, variance, flags = stamp["image"], stamp["variance"], stamp["flags"]
    yy, xx = np.mgrid[:64, :64]
    rr = np.hypot(xx-32, yy-32)
    finite = np.isfinite(image)
    annulus = (rr >= 10) & (rr <= 20) & finite
    if not np.any(annulus):
        raise RuntimeError(f"No finite 10-20 px background annulus for obs_id={row.get('obs_id')}")
    background = float(np.median(image[annulus]))
    search = (rr <= 10) & finite
    if not np.any(search):
        raise RuntimeError(f"No finite pixels within 10 px for obs_id={row.get('obs_id')}")
    peak_arr = np.where(search, image-background, -np.inf)
    py, px = np.unravel_index(int(np.argmax(peak_arr)), peak_arr.shape)
    sat = _saturation_mask(section["flag_header"], flags)
    centroid_region = (np.hypot(xx-px, yy-py) <= 3) & finite
    weights = np.where(centroid_region, np.maximum(image-background, 0), 0.0)
    if float(weights.sum()) <= 0:
        raise RuntimeError(f"Non-positive centroid weight for obs_id={row.get('obs_id')}")
    cx = float(np.sum(weights*xx)/np.sum(weights)); cy = float(np.sum(weights*yy)/np.sum(weights))
    xfull, yfull = origin[0]+cx, origin[1]+cy
    coord = section["wcs"].pixel_to_world(xfull, yfull)
    rasec, decsec = float(coord.ra.deg), float(coord.dec.deg)
    epix_full = section["wcs"].world_to_pixel(SkyCoord(rae*u.deg, dece*u.deg))
    dx, dy = xfull-float(epix_full[0]), yfull-float(epix_full[1])
    off_px = float(np.hypot(dx, dy))
    off_arcsec = float(ang_sep_deg(rae, dece, rasec, decsec)*3600)
    peak_var = float(variance[py, px])
    peak_snr = ((float(image[py, px])-background)/math.sqrt(peak_var)
                if np.isfinite(peak_var) and peak_var > 0 else None)
    return {"epoch": row.get("window_id"), "obs_id": row.get("obs_id"),
            "detector": f"D{_detector(row)}", "mjd": float(mjd),
            "ephemeris_ra_deg": rae, "ephemeris_dec_deg": dece,
            "measured_ra_deg": rasec, "measured_dec_deg": decsec,
            "offset_arcsec": off_arcsec, "offset_px": off_px,
            "offset_dx_px": dx, "offset_dy_px": dy,
            "peak_snr_variance": peak_snr, "peak_mjysr": float(image[py, px]),
            "background_mjysr": background, "peak_xy_stamp": [int(px), int(py)],
            "saturated_pixels_within_centroid": int(np.count_nonzero(sat & centroid_region)),
            "section_source": str(section.get("source", "unknown")),
            "ephemeris_source": str(ephrow.get("source", "unknown")),
            "access_url": row["access_url"]}


def run():
    epoch_rows = {}
    epoch_windows = {}
    truth_vals = []
    for epoch in ("1", "2"):
        window, chosen = _exposures_for_epoch(epoch)
        epoch_windows[epoch] = window
        measured = []
        for row, ephrow, mjd in chosen:
            try:
                m = _measure(row, ephrow, mjd)
                m["window_id"] = epoch
                measured.append(m)
                print(f"Measured window {epoch} {m['obs_id']} {m['detector']}: RA={m['measured_ra_deg']:.7f} Dec={m['measured_dec_deg']:.7f} offset={m['offset_arcsec']:.2f}\"")
            except Exception as exc:
                print(f"Exposure measurement failed ({row.get('obs_id')} D{_detector(row)}): {type(exc).__name__}: {exc}")
        epoch_rows[epoch] = measured
        if window.get("r_au"):
            truth_vals.append(float(window["r_au"]))
    if not epoch_rows["1"] or not epoch_rows["2"]:
        raise RuntimeError(f"Need measured exposures in both epochs; got A={len(epoch_rows['1'])}, B={len(epoch_rows['2'])}")
    truth = float(np.mean(truth_vals)) if truth_vals else float("nan")
    tA = [Time(m["mjd"], format="mjd", scale="utc") for m in epoch_rows["1"]]
    tB = [Time(m["mjd"], format="mjd", scale="utc") for m in epoch_rows["2"]]
    dgrid = np.geomspace(15, 1000, 1800)
    combos = []
    residuals_circ, residuals_static = [], []
    for ia, a in enumerate(epoch_rows["1"]):
        for ib, b in enumerate(epoch_rows["2"]):
            _check_time()
            dc, oc, grid = fit_distance(a["measured_ra_deg"], a["measured_dec_deg"], tA[ia],
                                        b["measured_ra_deg"], b["measured_dec_deg"], tB[ib],
                                        d_grid=dgrid, orbit="circular")
            ds, os, _ = fit_distance(a["measured_ra_deg"], a["measured_dec_deg"], tA[ia],
                                     b["measured_ra_deg"], b["measured_dec_deg"], tB[ib],
                                     d_grid=dgrid, orbit="static")
            combos.append({"epoch_a_obs_id": a["obs_id"], "epoch_a_detector": a["detector"],
                           "epoch_b_obs_id": b["obs_id"], "epoch_b_detector": b["detector"],
                           "d_fit_circular_au": dc, "d_fit_static_au": ds})
            residuals_circ.append(np.asarray(oc, float)); residuals_static.append(np.asarray(os, float))
    circ_d = np.asarray([c["d_fit_circular_au"] for c in combos])
    stat_d = np.asarray([c["d_fit_static_au"] for c in combos])
    circ_med = float(np.median(circ_d)); stat_med = float(np.median(stat_d))
    result = {"body": "neptune", "truth_r_au": truth,
              "truth_source": "mean r_au from window-1/window-2 ephemeris rows",
              "ephemeris_sources": sorted({m["ephemeris_source"] for rows in epoch_rows.values() for m in rows}),
              "pixel_scale_arcsec": PIXEL_ARCSEC,
              "exposures": epoch_rows, "combinations": combos,
              "n_combinations": len(combos),
              "circular": {"median_d_fit_au": circ_med,
                           "p16_p84_au": [float(x) for x in np.percentile(circ_d, [16, 84])],
                           "error_pct": 100*(circ_med-truth)/truth},
              "static": {"median_d_fit_au": stat_med,
                         "p16_p84_au": [float(x) for x in np.percentile(stat_d, [16, 84])],
                         "error_pct": 100*(stat_med-truth)/truth},
              "elapsed_seconds": round(time.monotonic()-START, 1)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/"astrometric_distance.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    # fit_distance returns per-combination residual curves on the supplied grid.
    curves = [("Our model (circular)", np.nanmedian(residuals_circ, axis=0), "#087e8b"),
              ("Parallax-only (static)", np.nanmedian(residuals_static, axis=0), "#d1495b")]
    fig, ax = plt.subplots(figsize=(11, 7), facecolor="white")
    ax.set_facecolor("white")
    for label, residual, color in curves:
        ax.plot(grid, residual, lw=3.0, color=color, label=label)
    ax.axvline(truth, color="#333333", ls="--", lw=2.2,
               label=f"Neptune, JPL {truth:.1f} AU")
    ax.axhline(PIXEL_ARCSEC, color="#666666", ls=":", lw=2.0,
               label="1 SPHEREx pixel (6.15\")")
    ax.set_xscale("log"); ax.set_yscale("log")
    ticks=[15,20,30,50,100,300,1000]
    ax.set_xticks(ticks); ax.set_xticklabels([str(x) for x in ticks])
    ax.set_xlabel("Assumed heliocentric distance (AU)", fontsize=16)
    ax.set_ylabel("Angular miss at epoch B (arcsec)", fontsize=16)
    ax.set_title("Real SPHEREx data — positions measured from images", fontsize=18, pad=16)
    ax.tick_params(axis="both", labelsize=13); ax.grid(True, which="both", alpha=.22)
    ax.legend(fontsize=12); fig.tight_layout()
    fig.savefig(OUT/"astrometric_residual.png", dpi=180, facecolor="white"); plt.close(fig)
    print("ASTROMETRY SUMMARY", json.dumps({k: result[k] for k in ("truth_r_au", "n_combinations", "circular", "static", "elapsed_seconds")}))
    return result


if __name__ == "__main__":
    run()
