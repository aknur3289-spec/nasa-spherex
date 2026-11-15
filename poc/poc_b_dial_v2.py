#!/usr/bin/env python
"""Variance-weighted, wavelength-matched PoC B rerun."""
from __future__ import annotations

import csv
import json
import math
import re
import time
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.time import Time
import astropy.units as u
from numpy.lib.stride_tricks import sliding_window_view

from spx.focus import dial_grid, summarize
from spx.geometry import ang_sep_deg, predict_radec
from spx.horizons import ephem
from realdata import (RAW, sia_frames, wavelength_at, wavelength_from_section)
from poc_b_dial import (OUT, POC, ROOT, SectionStore, StopRun, _best_target_for_distance,
                        _filter_exposures, _inside_region, _json_safe, _query_radius,
                        _unique_by_url)

BAD_FLAGS = {"TRANSIENT", "SUR_ERROR", "NONFUNC", "MISSING_DATA", "HOT", "COLD", "PERSIST",
             "OUTLIER", "CROSSTALK", "GHOST", "GHOST_FPA", "GHOST_EXT", "STREAK", "HALO"}
SAT_FLAGS = {"OVERFLOW", "NONLINEAR", "BLOOM"}
NEVER_MASK = {"SOURCE", "DICHROIC", "FULLSAMPLE", "PHANMISS"}
MAX_RUNTIME = 3600.0


def _detector(row):
    return int(re.search(r"D([1-6])_spx_", row["access_url"]).group(1))


def _family(row):
    return "short" if _detector(row) <= 3 else "long"


def _source_aperture(image, x, y, radius=2.5):
    yy, xx = np.mgrid[:image.shape[0], :image.shape[1]]
    r = np.hypot(xx-x, yy-y)
    aperture = (r <= radius) & np.isfinite(image)
    annulus = (r >= 5) & (r <= 9) & np.isfinite(image)
    if not np.any(aperture):
        return float("nan")
    background = float(np.median(image[annulus])) if np.any(annulus) else 0.0
    return float(np.sum(image[aperture] - background))


def _flag_policy(section, flags, image, variance):
    names = {}
    for key, value in section["flag_header"].items():
        if re.fullmatch(r"MSKN\d{4}", key):
            names[int(key[-4:])] = str(value).strip().upper()
    raw = np.asarray(flags)
    valid_flag = np.isfinite(raw)
    bits = np.where(valid_flag, np.rint(raw), 0).astype(np.int64)
    bad = np.zeros(bits.shape, dtype=bool)
    saturation = np.zeros(bits.shape, dtype=bool)
    source = np.zeros(bits.shape, dtype=bool)
    for bit, name in names.items():
        mask = (bits & (1 << bit)) != 0
        if name in BAD_FLAGS:
            bad |= mask
        elif name in SAT_FLAGS:
            saturation |= mask
        elif name == "SOURCE":
            source |= mask
    data = np.array(image, dtype=float, copy=True)
    var = np.array(variance, dtype=float, copy=True)
    finite = np.isfinite(data)
    stamp_max = float(np.nanmax(data[finite])) if np.any(finite) else float("nan")
    data[saturation] = stamp_max
    data[bad & ~saturation] = np.nan
    data[~valid_flag] = np.nan
    data[~finite] = np.nan
    var[bad & ~saturation] = np.nan
    var[~valid_flag] = np.nan
    return data, var, source, saturation, names


def _stamp_raw(section, ra, dec, size=64):
    x, y = section["wcs"].world_to_pixel(SkyCoord(float(ra)*u.deg, float(dec)*u.deg))
    xfull, yfull = float(x), float(y)
    xlocal, ylocal = xfull - section["x0"], yfull - section["y0"]
    n = size
    x0, y0 = int(round(xlocal))-n//2, int(round(ylocal))-n//2
    arrays = [section["image"], section["flags"], section.get("variance")]
    result = []
    for arr in arrays:
        out = np.full((n, n), np.nan, dtype=float)
        if arr is not None:
            xa, xb = max(0, x0), min(arr.shape[1], x0+n)
            ya, yb = max(0, y0), min(arr.shape[0], y0+n)
            if xa < xb and ya < yb:
                out[ya-y0:yb-y0, xa-x0:xb-x0] = arr[ya:yb, xa:xb]
        result.append(out)
    # Full-image pixel grid is needed to align the later template onto target pixels.
    x_grid = np.arange(n, dtype=float) + int(round(xfull))-n//2
    y_grid = np.arange(n, dtype=float) + int(round(yfull))-n//2
    gx, gy = np.meshgrid(x_grid, y_grid)
    return result[0], result[1], result[2], section["wcs"].pixel_to_world(gx, gy)


def _bilinear(arr, x, y, variance=False):
    ny, nx = arr.shape
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    dx, dy = x-x0, y-y0
    out = np.full(np.shape(x), np.nan, dtype=float)
    good = (x0 >= 0) & (y0 >= 0) & (x0+1 < nx) & (y0+1 < ny)
    if not np.any(good):
        return out
    inds = np.where(good)
    vals = [arr[y0[inds], x0[inds]], arr[y0[inds], x0[inds]+1],
            arr[y0[inds]+1, x0[inds]], arr[y0[inds]+1, x0[inds]+1]]
    weights = [(1-dy[inds])*(1-dx[inds]), (1-dy[inds])*dx[inds],
               dy[inds]*(1-dx[inds]), dy[inds]*dx[inds]]
    valid = np.logical_and.reduce([np.isfinite(v) for v in vals])
    values = np.zeros_like(weights[0])
    for w, v in zip(weights, vals):
        values += (w*w if variance else w) * v
    out[inds] = np.where(valid, values, np.nan)
    return out


def _align_template(target_section, template_section, ra, dec, target_raw, target_flags, target_var, sky_grid):
    tx, ty = template_section["wcs"].world_to_pixel(sky_grid)
    tx = np.asarray(tx, float) - template_section["x0"]
    ty = np.asarray(ty, float) - template_section["y0"]
    template_image = _bilinear(template_section["image"], tx, ty)
    template_var = _bilinear(template_section["variance"], tx, ty, variance=True)
    ix, iy = np.rint(tx).astype(int), np.rint(ty).astype(int)
    tflags = np.full(tx.shape, np.nan)
    inside = (ix >= 0) & (iy >= 0) & (ix < template_section["flags"].shape[1]) & (iy < template_section["flags"].shape[0])
    tflags[inside] = template_section["flags"][iy[inside], ix[inside]]
    # The output grid is the target grid. Reuse the target plane and its native flags.
    return template_image, tflags, template_var


def _top_matched_star_scale(target, template, center=(31.5, 31.5), count=5):
    valid = np.isfinite(target) & np.isfinite(template)
    if int(valid.sum()) < 100:
        return None, 0
    arr = np.where(valid, target, -np.inf)
    if min(arr.shape) < 7:
        return None, 0
    windows = sliding_window_view(arr, (7, 7))
    local_max = arr[3:-3, 3:-3] == np.max(windows, axis=(-2, -1))
    cy, cx = center
    peaks = []
    for yy, xx in zip(*np.where(local_max)):
        y, x = int(yy+3), int(xx+3)
        if np.hypot(x-cx, y-cy) < 20 or not valid[y, x] or target[y, x] <= 0:
            continue
        # Candidate must also be a local maximum in the aligned template nearby.
        y0, y1 = max(0, y-2), min(template.shape[0], y+3)
        x0, x1 = max(0, x-2), min(template.shape[1], x+3)
        patch = np.where(valid[y0:y1, x0:x1], template[y0:y1, x0:x1], -np.inf)
        if not patch.size or not np.isfinite(np.max(patch)):
            continue
        ty, tx = np.unravel_index(np.argmax(patch), patch.shape)
        sx, sy = x0+int(tx), y0+int(ty)
        if np.hypot(sx-x, sy-y) > 2:
            continue
        tf = _source_aperture(target, x, y)
        pf = _source_aperture(template, sx, sy)
        if np.isfinite(tf) and np.isfinite(pf) and tf > 0 and pf > 0:
            peaks.append((tf, pf, x, y))
    peaks.sort(reverse=True)
    selected = peaks[:count]
    if len(selected) < count:
        return None, 0
    ratio = float(np.median([a/b for a, b, _, _ in selected]))
    return ratio, len(selected)


def _variance_snr(diff, var_target, var_template, scale, search_radius=20, radius=2.5):
    valid = np.isfinite(diff) & np.isfinite(var_target) & np.isfinite(var_template)
    valid &= (var_target >= 0) & (var_template >= 0)
    yy, xx = np.mgrid[:diff.shape[0], :diff.shape[1]]
    cy, cx = (diff.shape[0]-1)/2, (diff.shape[1]-1)/2
    ann = (np.hypot(xx-cx, yy-cy) >= 7) & (np.hypot(xx-cx, yy-cy) <= 15) & valid
    background = float(np.median(diff[ann])) if np.any(ann) else 0.0
    # Convolve all possible apertures at once. Invalid pixels contribute neither
    # flux nor variance, keeping the requested variance expression explicit.
    kernel = (np.hypot(*np.mgrid[-int(radius):int(radius)+1,
                                 -int(radius):int(radius)+1]) <= radius).astype(float)
    flux_plane = np.where(valid, diff-background, 0.0)
    variance_plane = np.where(valid, var_target+scale**2*var_template, 0.0)
    pad = kernel.shape[0]//2
    fp = np.pad(flux_plane, pad)
    vp = np.pad(variance_plane, pad)
    fwin = sliding_window_view(fp, kernel.shape)
    vwin = sliding_window_view(vp, kernel.shape)
    flux_map = np.einsum("ijxy,xy->ij", fwin, kernel, optimize=True)
    variance_map = np.einsum("ijxy,xy->ij", vwin, kernel, optimize=True)
    search = np.hypot(xx-cx, yy-cy) <= search_radius
    snr_map = np.divide(flux_map, np.sqrt(variance_map), out=np.full_like(flux_map, -np.inf),
                        where=(variance_map > 0) & search)
    iy, ix = np.unravel_index(int(np.argmax(snr_map)), snr_map.shape)
    best = float(snr_map[iy, ix])
    best_off = float(np.hypot(ix-cx, iy-cy))
    return (float(best), float(best_off)) if np.isfinite(best) else (None, None)


def _unflagged_snr(image, variance, flags, flag_header):
    names = {int(k[-4:]): str(v).strip().upper() for k, v in flag_header.items()
             if re.fullmatch(r"MSKN\d{4}", k)}
    src_bits = [b for b, name in names.items() if name == "SOURCE"]
    mask = np.zeros(flags.shape, bool)
    for bit in src_bits:
        mask |= (np.asarray(flags, dtype=np.int64) & (1 << bit)) != 0
    img = np.asarray(image, float).copy(); var = np.asarray(variance, float).copy()
    img[mask] = np.nan; var[mask] = np.nan
    for bit, name in names.items():
        if name in BAD_FLAGS:
            bad = (np.asarray(flags, dtype=np.int64) & (1 << bit)) != 0
            img[bad] = np.nan; var[bad] = np.nan
    return _variance_snr(img, var, np.zeros_like(var), 0.0)


def _diagnostics(old, sanity_path):
    truth = float(old["truth_r_au"])
    grid = dial_grid(15, 1000, step_px=15)
    bands = [(15,25),(25,35),(35,60),(60,200),(200,1000)]
    band_report = {}
    for name, run in old["runs"].items():
        used_d = [float(s["distance_au"]) for s in run["steps"]]
        band_report[name] = {}
        for lo, hi in bands:
            total = sum(lo <= float(d) and (float(d) < hi or (hi == 1000 and float(d) <= hi)) for d in grid)
            used = sum(lo <= d and (d < hi or (hi == 1000 and d <= hi)) for d in used_d)
            skipped = total-used
            reasons = run["skipped_reasons"]
            # An exact per-band reason split was not stored in the original output.
            reason_hist = ({next(iter(reasons)): skipped} if len(reasons)==1
                           else {"reason_not_retained_per_distance": skipped})
            band_report[name][f"{lo}-{hi}"] = {"total": int(total), "used": int(used),
                                               "skipped": int(skipped), "reason_histogram": reason_hist}
    nearest = sorted(grid, key=lambda d: abs(float(d)-truth))[:10]
    nearest_rows = []
    for d in nearest:
        item = {"distance_au": round(float(d),2), "runs": {}}
        for name, run in old["runs"].items():
            found = next((s for s in run["steps"] if abs(float(s["distance_au"])-float(d)) < 0.011), None)
            if found:
                item["runs"][name] = {"status":"used", "snr_old":found["snr"]}
            else:
                reasons = run["skipped_reasons"]
                reason = next(iter(reasons)) if len(reasons)==1 else "reason_not_retained_per_distance"
                item["runs"][name] = {"status":"skipped", "reason":reason}
        nearest_rows.append(item)
    with fits.open(sanity_path, memmap=False) as hdul:
        image = np.asarray(hdul["IMAGE"].data, float)
        flags = np.asarray(hdul["FLAGS"].data, np.int64)
        header = hdul["FLAGS"].header
        names = {int(k[-4:]):str(v).strip().upper() for k,v in header.items() if re.fullmatch(r"MSKN\d{4}",k)}
        source_bits = [bit for bit,n in names.items() if n=="SOURCE"]
        cy,cx=44,43
        yy,xx=np.mgrid[:image.shape[0],:image.shape[1]]
        def bits_in_aperture(x,y):
            select=(xx-x)**2+(yy-y)**2<=9
            values=np.unique(flags[select]); ored=int(np.bitwise_or.reduce(flags[select].ravel()))
            present=[names[b] for b in names if ored&(1<<b)]
            return {"xy":[int(x),int(y)],"peak_mjysr":float(image[y,x]),
                    "flag_values":values.tolist(),"bits":present,
                    "source_set":any(ored&(1<<b) for b in source_bits)}
        windows=sliding_window_view(image,(7,7))
        localmax=image[3:-3,3:-3]==np.nanmax(windows,axis=(-2,-1))
        peaks=[]
        for y,x in zip(*np.where(localmax)):
            x,y=int(x+3),int(y+3)
            if np.isfinite(image[y,x]) and np.hypot(x-cx,y-cy)>8:
                peaks.append((float(image[y,x]),x,y))
        peaks.sort(reverse=True); stars=[]
        for _,x,y in peaks:
            if all((x-a[0])**2+(y-a[1])**2>49 for a in [(q["xy"][0],q["xy"][1]) for q in stars]):
                stars.append(bits_in_aperture(x,y))
            if len(stars)==3: break
        neptune=bits_in_aperture(cx,cy)
    result={"prior_skip_histograms":band_report,"closest_to_truth":nearest_rows,
            "sanity_neptune_pixels":neptune,"sanity_brightest_stars":stars,
            "source_flag_on_neptune":neptune["source_set"],
            "source_flag_on_stars":[s["source_set"] for s in stars],
            "unflagged_metric_applicable":bool(not neptune["source_set"] and any(s["source_set"] for s in stars))}
    print("DIAG skip reasons per run/per distance band:",json.dumps(band_report,sort_keys=True))
    print("DIAG 10 grid points nearest truth:",json.dumps(nearest_rows,sort_keys=True))
    print("DIAG Neptune flags within 3 px:",json.dumps(neptune,sort_keys=True))
    print("DIAG three brightest non-Neptune peaks:",json.dumps(stars,sort_keys=True))
    print("DIAG SOURCE set on Neptune:",neptune["source_set"],"on stars:",[s["source_set"] for s in stars])
    return result


def _summary_metric(steps, truth, metric="snr"):
    valid=[{"distance_au":s["distance_au"],"snr":s[metric]} for s in steps if s.get(metric) is not None]
    if not valid:
        return {"peak_distance_au":None,"err_pct":None,"peak_over_median":None,"peak_snr":None,"median_snr":None}
    return summarize(valid, truth_au=truth)


def _write_v2_json(payload):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"focus_neptune_v2.json").write_text(json.dumps(_json_safe(payload),indent=2,allow_nan=False)+"\n")


def _plot_v2(runs, truth, alt_enabled):
    fig,ax=plt.subplots(figsize=(10,6))
    positives=[s["snr"] for r in runs.values() for s in r["steps"] if s.get("snr") is not None and s["snr"]>0]
    ymin=max(min(positives)*0.5 if positives else 1e-3,1e-4)
    for name,run in runs.items():
        steps=run["steps"]
        if steps:
            vals=[s["snr"] if s["snr"] is not None and s["snr"]>0 else np.nan for s in steps]
            ax.plot([s["distance_au"] for s in steps],vals,marker=".",ms=2,lw=0.8,label=f"{name}: variance S/N")
            if alt_enabled:
                alt=[s.get("snr_unflagged") if s.get("snr_unflagged") and s["snr_unflagged"]>0 else np.nan for s in steps]
                ax.plot([s["distance_au"] for s in steps],alt,ls="--",lw=0.8,label=f"{name}: SOURCE-unflagged")
        skipped=run.get("skipped_steps",[])
        if skipped:
            ax.scatter([s["distance_au"] for s in skipped],[ymin]*len(skipped),marker="|",s=38,color="gray",alpha=.8)
    ax.axvline(truth,color="black",ls="--",lw=1,label=f"truth {truth:.2f} AU")
    ax.set_xscale("log");ax.set_yscale("log");ax.set_ylim(bottom=ymin)
    ax.set_xlabel("Assumed heliocentric distance (AU)");ax.set_ylabel("Variance-based aperture S/N")
    ax.set_title("SPHEREx Neptune distance dial v2 — wavelength matched")
    ax.grid(True,which="both",alpha=.22);ax.legend(fontsize=8);fig.tight_layout()
    fig.savefig(OUT/"focus_neptune_v2.png",dpi=160);plt.close(fig)


def _read_windows():
    with (POC/"windows_neptune.csv").open(newline="") as f:
        return {r["window_id"]:r for r in csv.DictReader(f)}


def _query_track_frames(ra0, dec0, t0, distances, window, control_dec_offset=0.0, track_window=None):
    """Query overlapping bounded SIA cones along the three dial tracks, caching rows."""
    cache_path=RAW/"sia_track_cache_v2.json"
    cache_path.parent.mkdir(parents=True,exist_ok=True)
    try: cache=json.loads(cache_path.read_text())
    except Exception: cache={}
    track_window=track_window or window
    tmid=Time((Time(track_window["start_utc"],scale="utc").mjd+Time(track_window["end_utc"],scale="utc").mjd)/2,
              format="mjd",scale="utc")
    candidates=[]
    for orbit,base_dec in (("circular",dec0),("static",dec0),("circular",dec0+control_dec_offset)):
        for d in distances:
            p=predict_radec(ra0,base_dec,t0,float(d),tmid,orbit)[0]
            if np.all(np.isfinite(p)):
                candidates.append((float(p[0]),float(p[1])))
    # Greedy spatial cover: every track point is within 2.5 degrees of a query
    # center, and each SIA cone has radius 2.8 degrees.
    remaining=list(candidates); centers=[]
    while remaining:
        center=remaining.pop(0); centers.append(center)
        remaining=[p for p in remaining if float(ang_sep_deg(center[0],center[1],p[0],p[1]))>2.5]
    result=[]
    for i,(ra,dec) in enumerate(centers,1):
        key=f"{window['start_utc']}|{window['end_utc']}|{ra:.6f}|{dec:.6f}|2.8"
        if key in cache:
            rows=cache[key]
            print(f"SIA cache {i}/{len(centers)} window {window['window_id']}: {len(rows)} rows")
        else:
            rows=sia_frames(ra,dec,2.8,window["start_utc"],window["end_utc"])
            cache[key]=rows
            cache_path.write_text(json.dumps(_json_safe(cache),separators=(",",":")))
            print(f"SIA query {i}/{len(centers)} window {window['window_id']}: center=({ra:.4f},{dec:.4f}) rows={len(rows)}")
        result.extend(rows)
    return _unique_by_url(result)


def _get_sanity_file():
    for p in (RAW).glob("*.fits"):
        try:
            with fits.open(p,memmap=False) as h:
                if h["IMAGE"].header.get("OBSID")=="2025W25_2A_0500_1":
                    return p
        except Exception:
            continue
    raise FileNotFoundError("cached window-1 sanity cutout not found")


def run_v2():
    start=time.monotonic()
    old=json.loads((OUT/"focus_neptune.json").read_text())
    diagnosis=_diagnostics(old,_get_sanity_file())
    refrow=None
    with (POC/"coverage_neptune.csv").open(newline="") as f:
        refrow=next(r for r in csv.DictReader(f) if r["window_id"]=="1" and r.get("obs_id")=="2025W25_2A_0500_1" and "D1_spx_" in r.get("access_url",""))
    ra0,dec0=float(old["ra0_deg"]),float(old["dec0_deg"])
    truth=float(old["truth_r_au"]);t0=Time(old["t0_utc"],scale="utc")
    distances=dial_grid(15,1000,step_px=15)
    windows=_read_windows();w2,w3=windows["2"],windows["3"]
    w2_mjd=(Time(w2["start_utc"],scale="utc").mjd,Time(w2["end_utc"],scale="utc").mjd)
    print(f"V2 bounded SIA track queries; {len(distances)} steps")
    all2=_query_track_frames(ra0,dec0,t0,distances,w2)
    all3=_query_track_frames(ra0,dec0,t0,distances,w3,control_dec_offset=1.0,track_window=w2)
    targets=_unique_by_url(_filter_exposures(all2,"spherex_dr1"))
    templates=_unique_by_url(_filter_exposures(all3,"spherex_qr3"))
    print("V2 candidate exposures:",len(targets),"DR1 targets;",len(templates),"QR3 templates")
    nep_template={}
    times=sorted({round(float(r["t_min"]),6) for r in templates})
    for i in range(0,len(times),100):
        if time.monotonic()-start>MAX_RUNTIME: raise StopRun("runtime exceeded 60 minutes")
        batch=times[i:i+100]
        ephs=ephem("neptune",[Time(m,format="mjd",scale="utc").isot for m in batch])
        nep_template.update({m:e for m,e in zip(batch,ephs)})

    defs=[("circular",ra0,dec0,"circular"),("static",ra0,dec0,"static"),
          ("empty_sky_control",ra0,dec0+1.0,"circular")]
    plans={};runs={n:{"steps":[],"skipped_steps":[],"attempted":0,"exposures":{}} for n,*_ in defs}
    for name,rra,rdec,orbit in defs:
        plan=[]
        for d in distances:
            if time.monotonic()-start>MAX_RUNTIME: raise StopRun("runtime exceeded 60 minutes")
            choice=_best_target_for_distance(rra,rdec,t0,float(d),orbit,targets)
            if choice is None:
                plan.append({"distance":float(d),"reason":"no_window2_coverage"});continue
            _,t1,row,pra,pdec=choice
            candidates=[r for r in templates if _family(r)==_family(row) and _inside_region(r.get("s_region",""),pra,pdec)]
            candidates.sort(key=lambda r:(0 if _detector(r)==_detector(row) else 1,float(r["t_min"])))
            valid_templates=[]
            for tr in candidates:
                neptune=nep_template.get(round(float(tr["t_min"]),6))
                if neptune is None: continue
                sep=float(ang_sep_deg(pra,pdec,neptune["ra_deg"],neptune["dec_deg"]))
                if sep>0.5: valid_templates.append((tr,sep))
            plan.append({"distance":float(d),"target":row,"t1_mjd":float(t1),"pred_ra":float(pra),
                         "pred_dec":float(pdec),"candidates":valid_templates})
        plans[name]=plan

    store=SectionStore(max_total=400)
    payload={"version":2,"body":"neptune","truth_r_au":truth,"t0_utc":t0.isot,
             "ra0_deg":ra0,"dec0_deg":dec0,"grid_n":len(distances),"diagnostics_prior":diagnosis,
             "unflagged_metric_applicable":diagnosis["unflagged_metric_applicable"],
             "runs":{},"sections_downloaded":0,"sections_served_by_source":store.source_counts.copy(),
             "wcs_wave_metadata_by_source":{},"elapsed_seconds":0.0,"stopped_reason":None}
    peak_stamps={}
    stop_reason=None
    try:
        # One target section per exposure covers all positions used by the three runs.
        target_needs={}
        for plan in plans.values():
            for item in plan:
                if "target" not in item: continue
                entry=target_needs.setdefault(item["target"]["access_url"],{"row":item["target"],"positions":[]})
                entry["positions"].append((item["pred_ra"],item["pred_dec"]))
        for i,entry in enumerate(target_needs.values(),1):
            if time.monotonic()-start>MAX_RUNTIME: raise StopRun("runtime exceeded 60 minutes")
            store.load(entry["row"],entry["positions"])
            if i%20==0 or i==len(target_needs): print(f"V2 target section {i}/{len(target_needs)}; sources={store.source_counts}; downloads={store.downloads}; elapsed={time.monotonic()-start:.1f}s")

        wave_sources={"local":set(),"s3":set(),"https":set(),"irsa":set()}
        for name,plan in plans.items():
            for item in plan:
                if "target" not in item: continue
                section=store.sections[item["target"]["access_url"]]
                try:
                    twave=wavelength_from_section(section,item["pred_ra"],item["pred_dec"])
                except Exception as exc:
                    item["reason"]="target_wcs_wave_unavailable";item["wave_error"]=repr(exc);continue
                item["target_wavelength_um"]=twave
                exact=[];fallback=[]
                for tr,sep in item["candidates"]:
                    if time.monotonic()-start>MAX_RUNTIME: raise StopRun("runtime exceeded 60 minutes")
                    emin=float(tr.get("em_min") or 0)*1e6;emax=float(tr.get("em_max") or 0)*1e6
                    if emin and emax and (twave < emin*0.95 or twave > emax*1.05): continue
                    try:
                        wtemp,wsource,werrors=wavelength_at(tr,item["pred_ra"],item["pred_dec"])
                    except Exception as exc:
                        item.setdefault("template_wave_errors",[]).append({"obs_id":tr.get("obs_id"),"error":repr(exc)})
                        continue
                    wave_sources.setdefault(wsource,set()).add(tr["access_url"])
                    frac=abs(wtemp-twave)/twave
                    entry={"row":tr,"sep":sep,"wave":wtemp,"frac":frac,"source":wsource}
                    if frac<=0.02: exact.append(entry)
                    elif frac<=0.05: fallback.append(entry)
                possible=exact if exact else fallback
                if not possible:
                    item["reason"]="no_lambda_match";continue
                possible.sort(key=lambda x:(x["frac"],0 if _detector(x["row"])==_detector(item["target"]) else 1,float(x["row"]["t_min"])))
                picked=possible[0]
                item.update({"template":picked["row"],"template_neptune_sep_deg":picked["sep"],
                             "template_wavelength_um":picked["wave"],"dlambda_frac":picked["frac"],
                             "dlambda_signed_frac":(picked["wave"]-twave)/twave,
                             "lambda_tolerance_used":0.02 if exact else 0.05,
                             "template_wave_source":picked["source"]})

        template_needs={}
        for plan in plans.values():
            for item in plan:
                if "template" not in item: continue
                entry=template_needs.setdefault(item["template"]["access_url"],{"row":item["template"],"positions":[]})
                entry["positions"].append((item["pred_ra"],item["pred_dec"]))
        for i,entry in enumerate(template_needs.values(),1):
            if time.monotonic()-start>MAX_RUNTIME: raise StopRun("runtime exceeded 60 minutes")
            store.load(entry["row"],entry["positions"])
            if i%20==0 or i==len(template_needs): print(f"V2 template section {i}/{len(template_needs)}; sources={store.source_counts}; downloads={store.downloads}; elapsed={time.monotonic()-start:.1f}s")

        alt_enabled=diagnosis["unflagged_metric_applicable"]
        for run_name,rra,rdec,orbit in defs:
            plan=plans[run_name];run=runs[run_name]
            for i,item in enumerate(plan,1):
                if time.monotonic()-start>MAX_RUNTIME: raise StopRun("runtime exceeded 60 minutes")
                run["attempted"]=i
                if i%20==0:
                    print(f"{run_name}: step {i}/{len(plan)}, d={item['distance']:.2f} AU, sections={store.downloads}, elapsed={time.monotonic()-start:.1f}s")
                    _save_outputs(payload,runs,store,truth,start,stop_reason,peak_stamps,alt_enabled,wave_sources)
                if item.get("reason"):
                    run["skipped_steps"].append({"distance_au":round(item["distance"],2),"reason":item["reason"]})
                    continue
                target=item["target"];template=item["template"]
                diff,detail=_difference_for_step(store,target,template,item["pred_ra"],item["pred_dec"])
                if detail is None:
                    run["skipped_steps"].append({"distance_au":round(item["distance"],2),"reason":"no_matched_stars"})
                    continue
                ratio,star_count,tar_img,tmpl_img,scaled,dvar_t,dvar_p,flags=detail
                snr,offset=_variance_snr(diff,dvar_t,dvar_p,ratio)
                if snr is None:
                    run["skipped_steps"].append({"distance_au":round(item["distance"],2),"reason":"invalid_variance_or_aperture"})
                    continue
                step={"distance_au":round(item["distance"],2),"pred":{"ra_deg":round(item["pred_ra"],6),"dec_deg":round(item["pred_dec"],6)},
                      "snr":round(float(snr),4),"offset_px":round(float(offset),3),
                      "target_obs_id":target.get("obs_id"),"target_collection":target.get("obs_collection"),
                      "target_detector":_detector(target),"target_t1_mjd":item["t1_mjd"],
                      "template_obs_id":template.get("obs_id"),"template_collection":template.get("obs_collection"),
                      "template_detector":_detector(template),"target_wavelength_um":item["target_wavelength_um"],
                      "template_wavelength_um":item["template_wavelength_um"],"dlambda_frac":item["dlambda_frac"],
                      "dlambda_signed_frac":item["dlambda_signed_frac"],"lambda_tolerance_used":item["lambda_tolerance_used"],
                      "template_scale":ratio,"matched_stars":star_count,"template_neptune_sep_deg":item["template_neptune_sep_deg"]}
                if alt_enabled:
                    uval,uoff=_unflagged_snr(tar_img,dvar_t,flags,store.sections[target["access_url"]]["flag_header"])
                    step["snr_unflagged"]=uval;step["snr_unflagged_offset_px"]=uoff
                else: step["snr_unflagged"]=None
                run["steps"].append(step)
                for row,role in ((target,"target"),(template,"template")):
                    run["exposures"][row["access_url"]]={"role":role,"obs_id":row.get("obs_id"),"collection":row.get("obs_collection"),
                                                               "detector":_detector(row),"access_url":row["access_url"]}
                if run_name=="circular":
                    oldpeak=peak_stamps.get("circular")
                    if oldpeak is None or snr>oldpeak["snr"]:
                        peak_stamps["circular"]={"snr":float(snr),"distance":step["distance_au"],"target":tar_img,
                                                   "template":scaled,"difference":diff,"ratio":ratio}
        stop_reason=None
    except StopRun as exc:
        stop_reason=str(exc);print("V2 STOP:",stop_reason)
    except Exception as exc:
        stop_reason=f"{type(exc).__name__}: {exc}";print("V2 ERROR (exact):",repr(exc))
    finally:
        _save_outputs(payload,runs,store,truth,start,stop_reason,peak_stamps,diagnosis["unflagged_metric_applicable"],locals().get("wave_sources",{}))


def _clean_stamp(section, ra, dec):
    image,flags,var,sky=_stamp_raw(section,ra,dec)
    clean,var_clean,source,sat,names=_flag_policy(section,flags,image,var)
    return clean,var_clean,flags,source,sat,sky


def _difference_for_step(store,target_row,template_row,ra,dec):
    target_sec=store.sections[target_row["access_url"]];template_sec=store.sections[template_row["access_url"]]
    tar,var_t,flags_t,source_t,sat_t,sky=_clean_stamp(target_sec,ra,dec)
    temp_raw,temp_flags,temp_var=_align_template(target_sec,template_sec,ra,dec,tar,flags_t,var_t,sky)
    temp,var_p,source_p,sat_p,_=_flag_policy(template_sec,temp_flags,temp_raw,temp_var)
    valid=np.isfinite(tar)&np.isfinite(temp)
    scale,nstars=_top_matched_star_scale(tar,temp)
    if scale is None or not np.isfinite(scale) or scale<=0:
        return None,None
    scaled=temp*scale
    diff=tar-scaled
    return diff,(scale,nstars,tar,temp,scaled,var_t,var_p,flags_t)


def _save_outputs(payload,runs,store,truth,start,stop_reason,peak_stamps,alt_enabled,wave_sources):
    serial_runs={}
    for name,run in runs.items():
        steps=run["steps"]
        run["skipped_count"]=len(run["skipped_steps"])
        run["steps_used"]=len(steps)
        run["skip_reason_histogram"]=dict(Counter(s["reason"] for s in run["skipped_steps"]))
        run["summary_variance_snr"]=_summary_metric(steps,truth,"snr")
        if alt_enabled:
            run["summary_snr_unflagged"]=_summary_metric(steps,truth,"snr_unflagged")
        serial_runs[name]={**run,"exposures":list(run["exposures"].values())}
    payload["runs"]=serial_runs
    payload["skipped_count"]=sum(len(r["skipped_steps"]) for r in runs.values())
    payload["sections_downloaded"]=store.downloads
    payload["section_cache_count_total"]=len({p.resolve() for p in store.section_dir.glob("*.fits")})
    payload["sections_served_by_source"]=store.source_counts.copy()
    payload["wcs_wave_metadata_by_source"]={k:len(v) for k,v in wave_sources.items()}
    payload["elapsed_seconds"]=round(time.monotonic()-start,1)
    payload["stopped_reason"]=stop_reason
    _write_v2_json(payload)
    _plot_v2(runs,truth,alt_enabled)
    peak=peak_stamps.get("circular")
    if peak:
        fig,axes=plt.subplots(1,3,figsize=(10,3.6))
        finite=np.concatenate([peak[k][np.isfinite(peak[k])] for k in ("target","template")])
        scale=max(float(np.percentile(finite,99.5)) if finite.size else 1.0,1e-12)
        for ax,key,title in zip(axes,("target","template","difference"),("Target","Aligned, scaled template","Difference")):
            im=peak[key];ax.imshow(np.arcsinh(np.maximum(im,0)/scale),origin="lower",cmap="gray")
            ax.axvline(31.5,color="cyan",lw=.7);ax.axhline(31.5,color="cyan",lw=.7);ax.set_title(title)
        fig.suptitle(f"Variance S/N peak {peak['distance']:.2f} AU; scale={peak['ratio']:.4g}")
        fig.tight_layout();fig.savefig(OUT/"peak_stamp_v2.png",dpi=150);plt.close(fig)


if __name__=="__main__":
    run_v2()
