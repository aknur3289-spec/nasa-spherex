#!/usr/bin/env python
"""PoC B-lite: measure Neptune astrometry in real SPHEREx exposure sections."""
from __future__ import annotations

import csv
import argparse
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


def _exposures_for_epoch(window_id, body="neptune"):
    with (POC / f"windows_{body}.csv").open(newline="") as f:
        window = next(r for r in csv.DictReader(f) if r["window_id"] == str(window_id))
    collection = "spherex_qr3" if str(window_id) == "3" else "spherex_dr1"
    with (POC / f"coverage_{body}.csv").open(newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("window_id") == str(window_id)
                and r.get("obs_collection") == collection
                and r.get("algorithm_name") == "exposure"
                and str(r.get("dataproduct_subtype", "")).lower() == "science"
                and _detector(r) is not None]
    by_mjd = {}
    for row in rows:
        by_mjd.setdefault(float(row["t_min"]), []).append(row)
    mjds = sorted(by_mjd)
    times = [Time(mjd, format="mjd", scale="utc").isot for mjd in mjds]
    eph_rows = ephem(body, times)
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
    print(f"Epoch {window_id}: {len(rows)} D1-D3 frames, {len(accepted)} contain {body.title()}, {len(chosen)} selected")
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


def run_body(body, epoch_a="1", epoch_b="2", output_suffix=None):
    """Run the same image-centroid astrometry workflow for a selected planet/pair."""
    global START,TIME_LIMIT
    START=time.monotonic()
    TIME_LIMIT=20*60 if body=="uranus" else 30*60
    awin, achoices = _exposures_for_epoch(epoch_a, body)
    bwin, bchoices = _exposures_for_epoch(epoch_b, body)
    epoch_rows={str(epoch_a):[],str(epoch_b):[]}
    for epoch, choices in ((str(epoch_a),achoices),(str(epoch_b),bchoices)):
        for row,ephrow,mjd in choices:
            try:
                m=_measure(row,ephrow,mjd);m["window_id"]=epoch
                epoch_rows[epoch].append(m)
                print(f"Measured {body} window {epoch} {m['obs_id']} {m['detector']}: RA={m['measured_ra_deg']:.7f} Dec={m['measured_dec_deg']:.7f} offset={m['offset_arcsec']:.2f}\"")
            except Exception as exc:
                print(f"Exposure measurement failed ({row.get('obs_id')} D{_detector(row)}): {type(exc).__name__}: {exc}")
    if not epoch_rows[str(epoch_a)] or not epoch_rows[str(epoch_b)]:
        raise RuntimeError(f"Need measured exposures in both epochs; got A={len(epoch_rows[str(epoch_a)])}, B={len(epoch_rows[str(epoch_b)])}")
    truth=float(np.mean([float(awin["r_au"]),float(bwin["r_au"])]))
    tA=[Time(m["mjd"],format="mjd",scale="utc") for m in epoch_rows[str(epoch_a)]]
    tB=[Time(m["mjd"],format="mjd",scale="utc") for m in epoch_rows[str(epoch_b)]]
    dgrid=np.geomspace(15,1000,1800)
    combos=[];residuals_circ=[];residuals_static=[]
    for ia,a in enumerate(epoch_rows[str(epoch_a)]):
        for ib,b in enumerate(epoch_rows[str(epoch_b)]):
            _check_time()
            dc,oc,grid=fit_distance(a["measured_ra_deg"],a["measured_dec_deg"],tA[ia],
                                    b["measured_ra_deg"],b["measured_dec_deg"],tB[ib],d_grid=dgrid,orbit="circular")
            ds,os,_=fit_distance(a["measured_ra_deg"],a["measured_dec_deg"],tA[ia],
                                 b["measured_ra_deg"],b["measured_dec_deg"],tB[ib],d_grid=dgrid,orbit="static")
            combos.append({"epoch_a_obs_id":a["obs_id"],"epoch_a_detector":a["detector"],
                           "epoch_b_obs_id":b["obs_id"],"epoch_b_detector":b["detector"],
                           "d_fit_circular_au":dc,"d_fit_static_au":ds})
            residuals_circ.append(np.asarray(oc,float));residuals_static.append(np.asarray(os,float))
    circ_d=np.asarray([c["d_fit_circular_au"] for c in combos]);static_d=np.asarray([c["d_fit_static_au"] for c in combos])
    circ_med=float(np.median(circ_d));static_med=float(np.median(static_d))
    suffix=output_suffix if output_suffix is not None else ("_uranus" if body=="uranus" else f"_{body}_w{epoch_a}{epoch_b}" if (epoch_a,epoch_b)!=("1","2") else "")
    result={"body":body,"epoch_a":str(epoch_a),"epoch_b":str(epoch_b),"truth_r_au":truth,
            "truth_source":f"mean r_au from windows_{body}.csv, windows {epoch_a} and {epoch_b}",
            "ephemeris_sources":sorted({m["ephemeris_source"] for xs in epoch_rows.values() for m in xs}),
            "pixel_scale_arcsec":PIXEL_ARCSEC,"exposures":epoch_rows,"combinations":combos,
            "n_combinations":len(combos),
            "circular":{"median_d_fit_au":circ_med,"p16_p84_au":[float(x) for x in np.percentile(circ_d,[16,84])],"error_pct":100*(circ_med-truth)/truth},
            "static":{"median_d_fit_au":static_med,"p16_p84_au":[float(x) for x in np.percentile(static_d,[16,84])],"error_pct":100*(static_med-truth)/truth},
            "elapsed_seconds":round(time.monotonic()-START,1)}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/f"astrometric_distance{suffix}.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    curves=[("Our model (circular)",np.nanmedian(residuals_circ,axis=0),"#087e8b"),
            ("Parallax-only (static)",np.nanmedian(residuals_static,axis=0),"#d1495b")]
    fig,ax=plt.subplots(figsize=(11,7),facecolor="white");ax.set_facecolor("white")
    for label,resid,color in curves:ax.plot(grid,resid,lw=3,color=color,label=label)
    ax.axvline(truth,color="#333",ls="--",lw=2.2,label=f"{body.title()}, JPL {truth:.1f} AU")
    ax.axhline(PIXEL_ARCSEC,color="#666",ls=":",lw=2,label="1 SPHEREx pixel (6.15\")")
    ticks=[15,20,30,50,100,300,1000];ax.set_xscale("log");ax.set_yscale("log");ax.set_xticks(ticks);ax.set_xticklabels([str(x) for x in ticks])
    ax.set_xlabel("Assumed heliocentric distance (AU)",fontsize=16);ax.set_ylabel("Angular miss at epoch B (arcsec)",fontsize=16)
    ax.set_title("Real SPHEREx data — positions measured from images",fontsize=18,pad=16)
    ax.tick_params(axis="both",labelsize=13);ax.grid(True,which="both",alpha=.22);ax.legend(fontsize=12);fig.tight_layout()
    fig.savefig(OUT/f"astrometric_residual{suffix}.png",dpi=180,facecolor="white");plt.close(fig)
    print(f"{body.upper()} ASTROMETRY SUMMARY",json.dumps({"truth_au":truth,"n_combinations":len(combos),"circular":result["circular"],"static":result["static"],"elapsed_seconds":result["elapsed_seconds"]}))
    return result


def _measure_local_cutout(row, local_root):
    """Apply the B-lite centroid rule to one Data Eng Neptune cutout."""
    path = local_root / str(row["local_path"])
    if not path.is_file():
        raise FileNotFoundError(f"local cutout does not exist: {path}")
    with fits.open(path, memmap=False) as hdul:
        image_hdu, flag_hdu, var_hdu = hdul["IMAGE"], hdul["FLAGS"], hdul["VARIANCE"]
        image = np.asarray(image_hdu.data, dtype=float)
        flags = np.asarray(flag_hdu.data)
        variance = np.asarray(var_hdu.data, dtype=float)
        wcs = __import__("astropy.wcs", fromlist=["WCS"]).WCS(image_hdu.header, fobj=hdul).celestial
        flag_header = flag_hdu.header.copy()
    rae, dece = float(row["eph_ra"]), float(row["eph_dec"])
    ex, ey = wcs.world_to_pixel(SkyCoord(rae*u.deg, dece*u.deg))
    yy, xx = np.mgrid[:image.shape[0], :image.shape[1]]
    rr = np.hypot(xx-float(ex), yy-float(ey))
    finite = np.isfinite(image)
    ann = (rr >= 10) & (rr <= 20) & finite
    search = (rr <= 10) & finite
    if not np.any(ann) or not np.any(search):
        raise RuntimeError(f"cutout lacks finite search/background pixels: {path}")
    background = float(np.median(image[ann]))
    peak_map = np.where(search, image-background, -np.inf)
    py, px = np.unravel_index(int(np.argmax(peak_map)), peak_map.shape)
    centroid = (np.hypot(xx-px, yy-py) <= 3) & finite
    weight = np.where(centroid, np.maximum(image-background, 0), 0)
    if float(weight.sum()) <= 0:
        raise RuntimeError(f"non-positive centroid weights: {path}")
    cx, cy = float(np.sum(weight*xx)/weight.sum()), float(np.sum(weight*yy)/weight.sum())
    measured = wcs.pixel_to_world(cx, cy)
    dx, dy = cx-float(ex), cy-float(ey)
    sat_mask = _saturation_mask(flag_header, flags)
    vp = float(variance[py, px])
    snr = (float(image[py, px])-background)/math.sqrt(vp) if np.isfinite(vp) and vp > 0 else None
    return {"obs_id": row["obs_id"], "detector": f"D{int(row['detector'])}",
            "window_id": row["window_id"], "mjd": float(row["mjd"]),
            "wavelength_um": float(row["wavelength_um"]), "bad_frac": float(row["bad_frac"]),
            "sat_frac": float(row["sat_frac"]), "eph_ra_deg": rae, "eph_dec_deg": dece,
            "measured_ra_deg": float(measured.ra.deg), "measured_dec_deg": float(measured.dec.deg),
            "offset_arcsec": float(ang_sep_deg(rae, dece, measured.ra.deg, measured.dec.deg)*3600),
            "offset_px": float(np.hypot(dx, dy)), "peak_snr_variance": snr,
            "peak_mjysr": float(image[py, px]), "background_mjysr": background,
            "saturated_pixels_within_centroid": int(np.count_nonzero(sat_mask & centroid)),
            "local_path": str(row["local_path"])}


def _fit_local_grid(a_rows, b_rows, d_grid, orbit):
    """Vectorized evaluation of fit_distance's same predict-and-minimize grid."""
    by_a = {}
    t_b = Time([float(b["mjd"]) for b in b_rows], format="mjd", scale="utc")
    for ia, a in enumerate(a_rows):
        pred_stack = np.empty((len(d_grid), len(b_rows), 2), dtype=float)
        ta = Time(float(a["mjd"]), format="mjd", scale="utc")
        for j, d in enumerate(d_grid):
            pred_stack[j] = predict_radec(float(a["measured_ra_deg"]), float(a["measured_dec_deg"]),
                                          ta, float(d), t_b, orbit)
        for ib, b in enumerate(b_rows):
            miss = ang_sep_deg(pred_stack[:, ib, 0], pred_stack[:, ib, 1],
                               float(b["measured_ra_deg"]), float(b["measured_dec_deg"])) * 3600
            ix = int(np.nanargmin(miss))
            by_a[(ia, ib)] = float(d_grid[ix])
    return by_a


def _stats(values, truth):
    vals = np.asarray(values, dtype=float)
    if vals.size == 0:
        return {"n_combinations": 0, "median_d_fit_au": None, "p16_p84_au": None, "error_pct": None}
    median = float(np.median(vals))
    return {"n_combinations": int(vals.size), "median_d_fit_au": median,
            "p16_p84_au": [float(x) for x in np.percentile(vals, [16, 84])],
            "error_pct": float(100*(median-truth)/truth)}


def run_neptune_all_local():
    """All quality-approved local Neptune cutouts; no network access."""
    local_root = Path.home() / "nasa-spherex"
    epochs_path = local_root / "data/meta/neptune/epochs.csv"
    with epochs_path.open(newline="") as f:
        raw = list(csv.DictReader(f))
    valid, skipped = [], []
    for row in raw:
        if row["status"] != "ok" or float(row["bad_frac"]) > 0.5:
            skipped.append({"obs_id": row["obs_id"], "status": row["status"],
                            "bad_frac": float(row["bad_frac"])})
        else:
            valid.append(row)
    exposures = {"1": [], "2": []}
    errors = []
    for i, row in enumerate(valid, 1):
        _check_time()
        try:
            exposures[row["window_id"]].append(_measure_local_cutout(row, local_root))
        except Exception as exc:
            errors.append({"obs_id": row["obs_id"], "error": f"{type(exc).__name__}: {exc}"})
        if i % 10 == 0:
            print(f"Local Neptune exposures {i}/{len(valid)} measured/attempted")
    if not exposures["1"] or not exposures["2"]:
        raise RuntimeError(f"No usable epochs after local cutout reads: A={len(exposures['1'])} B={len(exposures['2'])}")
    exposures["1"].sort(key=lambda x: (x["mjd"], x["detector"]))
    exposures["2"].sort(key=lambda x: (x["mjd"], x["detector"]))
    with (POC/"windows_neptune.csv").open(newline="") as f:
        win={r["window_id"]:r for r in csv.DictReader(f)}
    truth=float(np.mean([float(win["1"]["r_au"]),float(win["2"]["r_au"])]))
    grid=np.linspace(20.0,60.0,4000)
    step=float(grid[1]-grid[0])
    print(f"Grid: 4000 linear points 20–60 AU; step={step:.12f} AU")
    circ=_fit_local_grid(exposures["1"],exposures["2"],grid,"circular")
    static=_fit_local_grid(exposures["1"],exposures["2"],grid,"static")
    pairs=[]
    for (ia,ib),d in circ.items():
        pairs.append({"epoch_a_obs_id":exposures["1"][ia]["obs_id"],
                      "epoch_a_detector":exposures["1"][ia]["detector"],
                      "epoch_b_obs_id":exposures["2"][ib]["obs_id"],
                      "epoch_b_detector":exposures["2"][ib]["detector"],
                      "d_fit_circular_au":d,"d_fit_static_au":static[(ia,ib)]})
    by_detector={}
    for det in ("D1","D2","D3"):
        subset=[p for p in pairs if p["epoch_a_detector"]==det and p["epoch_b_detector"]==det]
        by_detector[det]={"circular":_stats([p["d_fit_circular_au"] for p in subset],truth),
                          "static":_stats([p["d_fit_static_au"] for p in subset],truth)}
    by_epoch_detector={}
    for det in ("D1","D2","D3"):
        a_subset=[p for p in pairs if p["epoch_a_detector"]==det]
        b_subset=[p for p in pairs if p["epoch_b_detector"]==det]
        by_epoch_detector[det]={
            "epoch_a_circular":_stats([p["d_fit_circular_au"] for p in a_subset],truth),
            "epoch_a_static":_stats([p["d_fit_static_au"] for p in a_subset],truth),
            "epoch_b_circular":_stats([p["d_fit_circular_au"] for p in b_subset],truth),
            "epoch_b_static":_stats([p["d_fit_static_au"] for p in b_subset],truth)}
    offsets=[x["offset_arcsec"] for e in exposures.values() for x in e]
    result={"body":"neptune","truth_r_au":truth,"truth_source":"mean r_au in windows_neptune.csv, windows 1 and 2",
            "n_input_rows":len(raw),"n_quality_skipped":len(skipped),"quality_skipped":skipped,
            "measurement_errors":errors,"fit_grid":{"n":4000,"min_au":20.0,"max_au":60.0,"step_au":step},
            "per_exposure_offset_arcsec":{"median":float(np.median(offsets)),"max":float(np.max(offsets))},
            "exposures":exposures,"n_combinations":len(pairs),"combinations":pairs,
            "circular":_stats([p["d_fit_circular_au"] for p in pairs],truth),
            "static":_stats([p["d_fit_static_au"] for p in pairs],truth),
            "by_same_detector":by_detector,"by_epoch_detector":by_epoch_detector,
            "elapsed_seconds":round(time.monotonic()-START,1)}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"astrometric_distance_all.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    fig,ax=plt.subplots(figsize=(10,6),facecolor="white")
    ax.hist([p["d_fit_circular_au"] for p in pairs],bins=36,alpha=.68,label="Circular orbit",color="#087e8b")
    ax.hist([p["d_fit_static_au"] for p in pairs],bins=36,alpha=.55,label="Parallax-only",color="#d1495b")
    ax.axvline(truth,color="#222222",ls="--",lw=2,label=f"Neptune truth {truth:.2f} AU")
    ax.set_xlabel("Fitted heliocentric distance (AU)",fontsize=14);ax.set_ylabel("Exposure combinations",fontsize=14)
    ax.set_title("Neptune astrometric distance from all local SPHEREx cutouts",fontsize=16)
    ax.legend(fontsize=12);ax.grid(axis="y",alpha=.2);fig.tight_layout()
    fig.savefig(OUT/"astrometric_hist_all.png",dpi=170,facecolor="white");plt.close(fig)
    print("ALL-LOCAL SUMMARY",json.dumps({"truth_au":truth,"n_combinations":len(pairs),
          "circular":result["circular"],"static":result["static"],"by_same_detector":by_detector,
          "offset_median_max_arcsec":result["per_exposure_offset_arcsec"],"elapsed_s":result["elapsed_seconds"]}))
    return result


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--all-local",action="store_true",help="fit all local Neptune meta cutouts")
    parser.add_argument("--body",choices=("neptune","uranus"),default="neptune")
    parser.add_argument("--epoch-a",default="1")
    parser.add_argument("--epoch-b",default="2")
    args=parser.parse_args()
    if args.all_local:
        run_neptune_all_local()
    elif args.body=="neptune" and args.epoch_a=="1" and args.epoch_b=="2":
        run()
    else:
        run_body(args.body,args.epoch_a,args.epoch_b)
