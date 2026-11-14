#!/usr/bin/env python
"""PoC B real-data sanity check. Per task time limit this stops before the grid."""
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
from astropy.time import Time
import astropy.units as u

from astropy.io import fits
from spx.geometry import predict_radec, ang_sep_deg
from spx.focus import dial_grid, focus_curve, summarize
from spx.horizons import ephem
from realdata import (cutout, read_cutout, sia_frames, stamp, read_section,
                      find_cached_section, local_exposure)

ROOT = Path(__file__).resolve().parents[1]
POC = Path(__file__).resolve().parent
OUT = POC / "out"


def _inside_region(region, ra, dec):
    """Point-in-polygon check in a small tangent-plane patch around target."""
    nums = [float(x) for x in re.findall(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?", region)]
    # Skip a potential leading token only if it was parsed as number (normally ICRS isn't).
    if len(nums) < 6 or len(nums) % 2:
        return False
    ras, decs = nums[0::2], nums[1::2]
    x = [((r - ra + 180) % 360 - 180) * np.cos(np.deg2rad(dec)) for r in ras]
    y = [d - dec for d in decs]
    tx = 0.0
    ty = 0.0
    inside = False
    j = len(x) - 1
    for i in range(len(x)):
        if ((y[i] > ty) != (y[j] > ty)) and tx < (x[j] - x[i]) * (ty - y[i]) / (y[j] - y[i]) + x[i]:
            inside = not inside
        j = i
    return inside


def _flag_descriptions(header):
    found = []
    for key, value in header.items():
        if re.fullmatch(r"MSKD\d{4}", key):
            try:
                bit = int(key[-4:])
            except ValueError:
                continue
            found.append((bit, str(value)))
    return found


def sanity_check():
    started = time.monotonic()
    with (POC / "windows_neptune.csv").open(newline="") as f:
        win = next(row for row in csv.DictReader(f) if row["window_id"] == "1")
    ra_mid, dec_mid = float(win["ra_deg"]), float(win["dec_deg"])
    # Reuse the observed single-exposure rows from the requested coverage input
    # to preselect window 1; never consider cube products.
    with (POC / "coverage_neptune.csv").open(newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["window_id"] == "1"
                and r.get("obs_collection") == "spherex_dr1"
                and r.get("algorithm_name") == "exposure"
                and r.get("dataproduct_subtype") == "science"
                and re.search(r"D[1-3]_spx_", r.get("access_url", ""))]
    if not rows:
        raise RuntimeError("No window-1 spherex_dr1 D1-D3 single-exposure science rows in poc/coverage_neptune.csv")

    # The SIA result was a cone query at the window midpoint. Resolve Neptune's
    # ephemeris at every candidate exposure's own MJD and require its footprint.
    times_mjd = sorted({float(r["t_min"]) for r in rows})
    times_iso = [Time(m, format="mjd", scale="utc").isot for m in times_mjd]
    eph_rows = ephem("neptune", times_iso)
    eph_by_time = {round(float(row["jd_utc"] - 2400000.5), 7): row for row in eph_rows}
    candidates = []
    for r in rows:
        mjd = float(r["t_min"])
        e = min(eph_rows, key=lambda item: abs((item["jd_utc"] - 2400000.5) - mjd))
        if _inside_region(r["s_region"], e["ra_deg"], e["dec_deg"]):
            candidates.append((r, e))
    if not candidates:
        raise RuntimeError("No D1-D3 window-1 exposure footprint contains Neptune at that exposure's t_min")
    # Choose the earliest valid single exposure; no cross-collection stack and
    # prefer the shortest-wavelength detector among available candidates.
    candidates.sort(key=lambda pair: (int(re.search(r"D([1-3])_spx_", pair[0]["access_url"]).group(1)), float(pair[0]["t_min"])))
    row, e = candidates[0]
    t0 = Time(float(row["t_min"]), format="mjd", scale="utc")
    print("SANITY exposure:", row["obs_id"], row["obs_collection"], row["access_url"])
    print("SANITY exact exposure time (UTC):", t0.isot, "MJD", float(row["t_min"]))
    print("SANITY Neptune ephemeris at t_min:", {k: e[k] for k in ("ra_deg", "dec_deg", "r_au", "delta_au", "source")})
    n_before = len(list((ROOT / "data" / "raw").glob("*.fits"))) if (ROOT / "data" / "raw").exists() else 0
    path = cutout(row["access_url"], e["ra_deg"], e["dec_deg"], 0.15)
    image, flags, wcs, wavelength_um = read_cutout(path)
    n_after = len(list((ROOT / "data" / "raw").glob("*.fits")))
    px, py = wcs.world_to_pixel(SkyCoord(e["ra_deg"]*u.deg, e["dec_deg"]*u.deg))
    cx, cy = int(round(float(px))), int(round(float(py)))
    x0, x1, y0, y1 = max(0, cx-2), min(image.shape[1], cx+3), max(0, cy-2), min(image.shape[0], cy+3)
    center_image = image[y0:y1, x0:x1]
    center_flags = flags[y0:y1, x0:x1]
    print("SANITY cutout:", path, "shape", image.shape, "centre pixel (x,y)", (cx, cy), "wavelength_um", wavelength_um)
    print("SANITY IMAGE pixel values (5x5 near centre; MJy/sr):\n", center_image)
    print("SANITY FLAGS raw values (5x5 near centre):\n", center_flags)
    unique, counts = np.unique(center_flags, return_counts=True)
    print("SANITY FLAGS value counts:", dict(zip(unique.tolist(), counts.tolist())))
    with __import__("astropy.io.fits", fromlist=["fits"]).open(path) as hdul:
        flag_header = hdul["FLAGS"].header
        bits = _flag_descriptions(flag_header)
        print("SANITY FLAGS definitions (MSKD keywords):", bits)
    finite = np.isfinite(image)
    local = image[max(0,cy-10):min(image.shape[0],cy+11), max(0,cx-10):min(image.shape[1],cx+11)]
    ring = local.copy()
    if ring.shape[0] > 10 and ring.shape[1] > 10:
        ring[4:-4, 4:-4] = np.nan
    peak = float(np.nanmax(center_image)) if center_image.size else float("nan")
    background = float(np.nanmedian(ring))
    print("SANITY central bright-source check: peak_MJy_sr=", peak, "local_ring_median_MJy_sr=", background,
          "peak/background=", (peak/background if background else float("inf")))
    sat_bits = [bit for bit, name in bits if "SATUR" in name.upper()]
    center_flag_or = int(np.bitwise_or.reduce(center_flags.astype(np.int64).ravel())) if center_flags.size else 0
    print("SANITY saturation definitions:", sat_bits, "centre_flag_OR:", center_flag_or,
          "saturation_bit_present:", any(center_flag_or & (1 << bit) for bit in sat_bits))
    print("SANITY cutouts downloaded this run:", n_after - n_before)

    fig, ax = plt.subplots(figsize=(6, 6))
    stretch = np.arcsinh(np.maximum(image, 0) / max(np.nanpercentile(image[finite], 99.5), 1e-12))
    ax.imshow(stretch, origin="lower", cmap="gray", interpolation="nearest")
    ax.axvline(px, color="cyan", lw=0.8)
    ax.axhline(py, color="cyan", lw=0.8)
    ax.set_title(f"SPHEREx {row['obs_id']} D{re.search(r'D([1-3])_spx_', row['access_url']).group(1)}; Neptune at exposure time")
    ax.set_xlabel("cutout pixel x"); ax.set_ylabel("cutout pixel y")
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "sanity_window1.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("SANITY elapsed_seconds:", round(time.monotonic() - started, 1))
    return row, e, t0, image, wcs


def _near_center_peak(arr, radius=3):
    yy, xx = np.mgrid[:arr.shape[0], :arr.shape[1]]
    cy, cx = (arr.shape[0] - 1) / 2, (arr.shape[1] - 1) / 2
    vals = np.asarray(arr, dtype=float)
    sel = np.hypot(yy-cy, xx-cx) <= radius
    if not np.any(sel & np.isfinite(vals)):
        return float("nan"), (None, None), float("nan"), float("nan")
    inds = np.where(sel, vals, -np.inf)
    iy, ix = np.unravel_index(np.argmax(inds), inds.shape)
    ann = (np.hypot(yy-cy, xx-cx) >= 6) & (np.hypot(yy-cy, xx-cx) <= 15) & np.isfinite(vals)
    background = float(np.median(vals[ann])) if np.any(ann) else float("nan")
    mad = float(1.4826*np.median(np.abs(vals[ann]-background))) if np.any(ann) else float("nan")
    z = (float(vals[iy, ix])-background)/mad if mad and np.isfinite(mad) else float("inf")
    return float(vals[iy, ix]), (int(ix), int(iy)), background, z


def identity_check(reference_row, eph0, target_image, target_wcs):
    """Compare the same reference sky position in a later survey pass."""
    ra0, dec0 = float(eph0["ra_deg"]), float(eph0["dec_deg"])
    with (POC / "windows_neptune.csv").open(newline="") as f:
        w3 = next(r for r in csv.DictReader(f) if r["window_id"] == "3")
    frames = sia_frames(ra0, dec0, 0.05, w3["start_utc"], w3["end_utc"])
    candidates = [r for r in frames if str(r.get("obs_collection", "")).lower() == "spherex_qr3"
                  and r.get("algorithm_name") == "exposure"
                  and str(r.get("dataproduct_subtype", "")).lower() == "science"
                  and re.search(r"D[1-3]_spx_", str(r.get("access_url", "")))]
    if not candidates:
        raise RuntimeError("No window-3 spherex_qr3 D1-D3 single-exposure science frame covers the window-1 sky position")
    det0 = re.search(r"D([1-3])_spx_", reference_row["access_url"]).group(1)
    candidates.sort(key=lambda r: (0 if re.search(r"D([1-3])_spx_", r["access_url"]).group(1) == det0 else 1,
                                  float(r["t_min"])))
    template_row = candidates[0]
    tpath = cutout(template_row["access_url"], ra0, dec0, 0.15)
    template_image, template_flags, template_wcs, template_wave = read_cutout(tpath)
    target_stamp = stamp(target_image, target_wcs, ra0, dec0, 64)
    template_stamp = stamp(template_image, template_wcs, ra0, dec0, 64)
    p0, xy0, bg0, z0 = _near_center_peak(target_stamp)
    p3, xy3, bg3, z3 = _near_center_peak(template_stamp)
    print("IDENTITY window-3 frame:", template_row["obs_id"], template_row["obs_collection"], template_row["access_url"])
    print("IDENTITY same-position peak within 3 px (window 1):", p0, "at", xy0, "background", bg0, "robust_sigma", z0)
    print("IDENTITY same-position peak within 3 px (window 3):", p3, "at", xy3, "background", bg3, "robust_sigma", z3)
    print("IDENTITY wavelengths (um): target 1.120093 from sanity read; template", template_wave)
    shared = np.concatenate([target_stamp[np.isfinite(target_stamp)], template_stamp[np.isfinite(template_stamp)]])
    scale = float(np.nanpercentile(shared, 99.5)) if shared.size else 1.0
    scale = max(scale, 1e-12)
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.5))
    for ax, data, title in zip(axes, (target_stamp, template_stamp),
                               ("Window 1 target", "Window 3 same sky position")):
        shown = np.arcsinh(np.maximum(data, 0)/scale)
        ax.imshow(shown, origin="lower", cmap="gray", vmin=0, vmax=np.arcsinh(1), interpolation="nearest")
        ax.axvline((data.shape[1]-1)/2, color="cyan", lw=0.7)
        ax.axhline((data.shape[0]-1)/2, color="cyan", lw=0.7)
        ax.set_title(title); ax.set_xlabel("pixel x")
    axes[0].set_ylabel("pixel y")
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "identity_check.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    # Centered source is present if a compact peak remains >5 robust sigma above
    # the same-stamp annulus. This is an explicit detection check, independent of
    # the desired distance-grid result.
    remains = np.isfinite(p3) and z3 >= 5
    print("IDENTITY source remains at same position:", remains, "(criterion: centered peak >=5 robust annulus sigmas)")
    return remains


class StopRun(Exception):
    pass


class SectionStore:
    """One cached bounded section per exposure, covering every planned stamp."""
    def __init__(self, max_total=400):
        self.max_total = max_total
        RAW = ROOT / "data" / "raw"
        RAW.mkdir(parents=True, exist_ok=True)
        self.section_dir = RAW / "sections"
        self.section_dir.mkdir(parents=True, exist_ok=True)
        self.cache_files = {p.resolve() for p in self.section_dir.glob("*.fits")}
        self.initial_total = len(self.cache_files)
        self.downloads = 0
        self.sections: dict[str, dict] = {}
        self.source_counts = {"local": 0, "s3": 0, "https": 0, "irsa": 0}
        self.source_errors = []

    def load(self, row, positions):
        url = row["access_url"]
        if url in self.sections:
            return self.sections[url]
        local_path = local_exposure(row)
        cached = None if local_path is not None else find_cached_section(row, positions)
        if cached is not None:
            section = cached
        else:
            if local_path is None and self.downloads >= self.max_total:
                raise StopRun(f"section download limit reached ({self.max_total})")
            section = read_section(row, positions)
            if section["source"] != "local" and not section.get("cache_hit"):
                self.downloads += 1
        source = section["source"].split(":", 1)[-1]
        if source in self.source_counts:
            self.source_counts[source] += 1
        self.source_errors.extend(section.get("errors", []))
        self.sections[url] = section
        return section

    @staticmethod
    def _stamp(section, ra, dec):
        x, y = section["wcs"].world_to_pixel(SkyCoord(float(ra)*u.deg, float(dec)*u.deg))
        x, y = float(x) - section["x0"], float(y) - section["y0"]
        n = 64
        x0, y0 = int(round(x)) - n//2, int(round(y)) - n//2
        out_image = np.full((n, n), np.nan, dtype=float)
        out_flags = np.full((n, n), np.nan, dtype=float)
        image, flags = section["image"], section["flags"]
        xa, xb = max(0, x0), min(image.shape[1], x0+n)
        ya, yb = max(0, y0), min(image.shape[0], y0+n)
        if xa < xb and ya < yb:
            out_image[ya-y0:yb-y0, xa-x0:xb-x0] = image[ya:yb, xa:xb]
            out_flags[ya-y0:yb-y0, xa-x0:xb-x0] = flags[ya:yb, xa:xb]
        return out_image, out_flags

    @classmethod
    def _clean(cls, section, ra, dec):
        img, flg = cls._stamp(section, ra, dec)
        valid_flags = np.isfinite(flg)
        f = np.where(valid_flags, np.rint(flg), 0).astype(np.int64)
        names = {}
        for key, name in section["flag_header"].items():
            if re.fullmatch(r"MSKN\d{4}", key):
                names[int(key[-4:])] = str(name).upper()
        bad_names = {"TRANSIENT", "SUR_ERROR", "NONFUNC", "MISSING_DATA", "HOT", "COLD", "PERSIST",
                     "OUTLIER", "CROSSTALK", "GHOST", "GHOST_FPA", "GHOST_EXT", "STREAK", "HALO"}
        saturation_names = {"OVERFLOW", "NONLINEAR", "BLOOM"}
        sat_bits = [bit for bit, name in names.items() if name in saturation_names]
        bad_bits = [bit for bit, name in names.items() if name in bad_names]
        saturated = np.zeros(f.shape, dtype=bool)
        for bit in sat_bits:
            saturated |= (f & (1 << bit)) != 0
        bad = np.zeros(f.shape, dtype=bool)
        for bit in bad_bits:
            bad |= (f & (1 << bit)) != 0
        finite = np.isfinite(img)
        maxval = float(np.nanmax(img[finite])) if np.any(finite) else float("nan")
        out = np.array(img, dtype=float, copy=True)
        out[saturated] = maxval
        out[bad & ~saturated] = np.nan
        out[~valid_flags] = np.nan
        out[~finite] = np.nan
        return out

    def difference_stamp(self, target_row, template_row, ra, dec):
        target_section = self.sections[target_row["access_url"]]
        template_section = self.sections[template_row["access_url"]]
        a = self._clean(target_section, ra, dec)
        b = self._clean(template_section, ra, dec)
        matched = np.isfinite(a) & np.isfinite(b) & (b > 0) & (a > 0)
        if int(matched.sum()) < 25:
            return None, (a, b, None, float("nan"), target_section, template_section)
        ratios = a[matched] / b[matched]
        ratios = ratios[np.isfinite(ratios) & (ratios > 0)]
        if ratios.size < 25:
            return None, (a, b, None, float("nan"), target_section, template_section)
        ratio = float(np.median(ratios))
        scaled = b * ratio
        diff = a - scaled
        return diff, (a, scaled, diff, ratio, target_section, template_section)


def _distance_from_reference(ra, dec, ra0, dec0):
    return float(ang_sep_deg(ra0, dec0, ra, dec))


def _filter_exposures(rows, collection):
    return [r for r in rows
            if str(r.get("obs_collection", "")).lower() == collection
            and r.get("algorithm_name") == "exposure"
            and str(r.get("dataproduct_subtype", "")).lower() == "science"
            and re.search(r"D[1-3]_spx_", str(r.get("access_url", "")))
            and "_cube" not in str(r.get("obs_collection", "")).lower()]


def _query_radius(ra0, dec0, distances, time_range, orbit, extra=1.0):
    times = Time(np.linspace(float(time_range[0]), float(time_range[1]), 5), format="mjd", scale="utc")
    max_sep = 0.0
    for d in (float(distances[0]), float(distances[-1]), 30.0):
        if d < float(distances[0]) or d > float(distances[-1]):
            continue
        positions = predict_radec(ra0, dec0, Time(60848.016684, format="mjd", scale="utc"), d, times, orbit)
        max_sep = max(max_sep, float(np.nanmax(ang_sep_deg(ra0, dec0, positions[:, 0], positions[:, 1]))))
    return max_sep + extra


def _unique_by_url(rows):
    return list({str(r.get("access_url")): r for r in rows}.values())


def _best_target_for_distance(ra0, dec0, t0, distance, orbit, target_rows):
    times = sorted({float(r["t_min"]) for r in target_rows})
    if not times:
        return None
    eph_positions = predict_radec(ra0, dec0, t0, float(distance),
                                  Time(times, format="mjd", scale="utc"), orbit)
    by_time = {round(t, 6): p for t, p in zip(times, eph_positions)}
    possible = []
    for row in target_rows:
        pos = by_time[round(float(row["t_min"]), 6)]
        if _inside_region(row.get("s_region", ""), float(pos[0]), float(pos[1])):
            det = int(re.search(r"D([1-3])_spx_", row["access_url"]).group(1))
            possible.append((det, float(row["t_min"]), row, float(pos[0]), float(pos[1])))
    if not possible:
        return None
    possible.sort(key=lambda x: (x[0], x[1]))
    return possible[0]


def _ephemeris_map(mjds):
    keys = sorted({round(float(m), 6) for m in mjds})
    mapped = {}
    for i in range(0, len(keys), 100):
        batch = keys[i:i+100]
        date_strings = [Time(m, format="mjd", scale="utc").isot for m in batch]
        values = ephem("neptune", date_strings)
        for m, row in zip(batch, values):
            mapped[m] = row
    return mapped


def _summary(steps, truth):
    if not steps:
        return {"peak_distance_au": None, "err_pct": None, "peak_over_median": None,
                "peak_snr": None, "median_snr": None, "pass": False}
    return summarize(steps, truth_au=truth)


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None
    return value


def _write_json(payload):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "focus_neptune.json"
    path.write_text(json.dumps(_json_safe(payload), indent=2, allow_nan=False) + "\n")


def _plot_outputs(all_runs, truth, peak_payload):
    OUT.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for name, run in all_runs.items():
        steps = run["steps"]
        if steps:
            ax.plot([s["distance_au"] for s in steps], [s["snr"] for s in steps], marker=".", ms=3, lw=1, label=name)
    ax.axvline(truth, color="black", ls="--", lw=1, label=f"truth {truth:.2f} AU")
    ax.set_xscale("log"); ax.set_xlabel("Assumed heliocentric distance (AU)"); ax.set_ylabel("Peak aperture S/N")
    ax.grid(True, which="both", alpha=0.25); ax.legend(); ax.set_title("SPHEREx Neptune distance dial")
    fig.tight_layout(); fig.savefig(OUT / "focus_neptune.png", dpi=160); plt.close(fig)
    if peak_payload:
        a, b, diff, detail = peak_payload
        fig, axes = plt.subplots(1, 3, figsize=(10, 3.8))
        finite = np.concatenate([a[np.isfinite(a)], b[np.isfinite(b)]])
        scale = max(float(np.nanpercentile(finite, 99.5)) if finite.size else 1.0, 1e-12)
        for ax, data, title in zip(axes, (a, b, diff), ("Target", "Scaled template", "Difference")):
            shown = np.arcsinh(np.maximum(data, 0)/scale)
            ax.imshow(shown, origin="lower", cmap="gray", interpolation="nearest")
            ax.axvline((data.shape[1]-1)/2, color="cyan", lw=0.7); ax.axhline((data.shape[0]-1)/2, color="cyan", lw=0.7)
            ax.set_title(title)
        fig.suptitle(f"{detail['run']} peak at {detail['distance_au']:.2f} AU; ratio={detail['template_scale']:.3g}")
        fig.tight_layout(); fig.savefig(OUT / "peak_stamp.png", dpi=160); plt.close(fig)
    else:
        (OUT / "peak_stamp.png").unlink(missing_ok=True)


def run_grid(reference_row, eph0, t0, identity_summary=None):
    started = time.monotonic()
    ra0, dec0 = float(eph0["ra_deg"]), float(eph0["dec_deg"])
    truth = float(eph0["r_au"])
    distances = dial_grid(15, 1000, step_px=15)
    win_rows = {}
    with (POC / "windows_neptune.csv").open(newline="") as f:
        win_rows = {r["window_id"]: r for r in csv.DictReader(f)}
    w2, w3 = win_rows["2"], win_rows["3"]
    w2_mjd = (Time(w2["start_utc"], scale="utc").mjd, Time(w2["end_utc"], scale="utc").mjd)
    max_radius = 0.0
    for base_dec, orbit in ((dec0, "circular"), (dec0, "static"), (dec0+1, "circular")):
        max_radius = max(max_radius, _query_radius(ra0, base_dec, distances, w2_mjd, orbit, extra=0.5))
    query_radius = min(max_radius + 1.2, 25.0)
    print(f"TRACK SIA query envelope radius_deg={query_radius:.4f}; grid steps={len(distances)}")
    all_rows = sia_frames(ra0, dec0, query_radius, w2["start_utc"], w2["end_utc"])
    win3_rows = sia_frames(ra0, dec0, query_radius, w3["start_utc"], w3["end_utc"])
    target_rows = _unique_by_url(_filter_exposures(all_rows, "spherex_dr1"))
    template_rows = _unique_by_url(_filter_exposures(win3_rows, "spherex_qr3"))
    print("TRACK single-exposure candidates:", len(target_rows), "window-2 DR1;", len(template_rows), "window-3 QR3")

    # Resolve Neptune at candidate frame times for the template exclusion rule.
    nep_at_template = _ephemeris_map([float(r["t_min"]) for r in template_rows])
    grid_defs = [
        ("circular", ra0, dec0, "circular"),
        ("static", ra0, dec0, "static"),
        ("empty_sky_control", ra0, dec0+1.0, "circular"),
    ]
    tiles = SectionStore(max_total=400)
    baseline_downloads = tiles.initial_total
    runs = {name: {"steps": [], "attempted": 0, "skipped": 0, "skipped_reasons": {}, "exposures": {}}
            for name, *_ in grid_defs}
    payload = {"body": "neptune", "ephemeris_source": eph0.get("source"), "t0_utc": t0.isot,
               "ra0_deg": ra0, "dec0_deg": dec0, "truth_r_au": truth, "grid_n": len(distances),
               "identity_check": identity_summary or {"same_position_source_remains": False}, "runs": {},
               "skipped_count": 0, "section_cache_count_start": baseline_downloads,
               "sections_downloaded": tiles.downloads, "sections_served_by_source": tiles.source_counts.copy(),
               "elapsed_seconds": 0.0, "stopped_reason": None}
    peak_payload = None
    global_stop = None
    processed_any = 0

    # Cache exact predicted positions per candidate frame, then select only
    # footprints containing the predicted sky coordinate at that row's t_min.
    planned = {}
    all_template_mjds = []
    for name, run_ra, run_dec, orbit in grid_defs:
        plan = []
        for idx, d in enumerate(distances):
            choice = _best_target_for_distance(run_ra, run_dec, t0, float(d), orbit, target_rows)
            if choice is None:
                plan.append(None)
                continue
            _, target_mjd, target_row, pred_ra, pred_dec = choice
            matches = [r for r in template_rows if _inside_region(r.get("s_region", ""), pred_ra, pred_dec)]
            matches.sort(key=lambda r: (0 if re.search(r"D([1-3])_spx_", r["access_url"]).group(1)
                                        == re.search(r"D([1-3])_spx_", target_row["access_url"]).group(1) else 1,
                                        float(r["t_min"])))
            matches = matches[:8]
            all_template_mjds.extend(float(r["t_min"]) for r in matches)
            plan.append({"distance": float(d), "target": target_row, "t1_mjd": target_mjd,
                         "pred_ra": pred_ra, "pred_dec": pred_dec, "templates": matches})
        planned[name] = plan
    # ephemerides have already been requested for all candidate template times;
    # no per-step Horizons round trips occur during scoring.
    for run_name, plan in planned.items():
        for step in plan:
            if not step:
                continue
            selected = None
            det_target = re.search(r"D([1-3])_spx_", step["target"]["access_url"]).group(1)
            for tr in step["templates"]:
                neptune = nep_at_template.get(round(float(tr["t_min"]), 6))
                if neptune is None:
                    continue
                sep = ang_sep_deg(step["pred_ra"], step["pred_dec"], neptune["ra_deg"], neptune["dec_deg"])
                if sep > 0.5:
                    selected = tr
                    step["template_neptune_sep_deg"] = float(sep)
                    break
            step["template"] = selected

    initial_plan_time = time.monotonic() - started
    print(f"TRACK planning done in {initial_plan_time:.1f}s; section downloads start at {tiles.downloads}")

    try:
        needed = {}
        for plan in planned.values():
            for item in plan:
                if item is None or item.get("template") is None:
                    continue
                position = (item["pred_ra"], item["pred_dec"])
                for row in (item["target"], item["template"]):
                    entry = needed.setdefault(row["access_url"], {"row": row, "positions": []})
                    entry["positions"].append(position)
        print(f"SECTION read plan: {len(needed)} distinct exposures; one bounding section per exposure")
        for index, entry in enumerate(needed.values(), 1):
            if time.monotonic() - started >= 3600:
                raise StopRun("runtime exceeded 60 minutes")
            tiles.load(entry["row"], entry["positions"])
            if index % 20 == 0 or index == len(needed):
                print(f"section {index}/{len(needed)}, source counts={tiles.source_counts}, section downloads={tiles.downloads}, elapsed={time.monotonic()-started:.1f}s")

        for run_name, run_ra, run_dec, orbit in grid_defs:
            plan = planned[run_name]
            output = runs[run_name]
            n = len(plan)
            for i, item in enumerate(plan, 1):
                processed_any += 1
                output["attempted"] = i
                if time.monotonic() - started >= 3600:
                    raise StopRun("runtime exceeded 60 minutes")
                if i % 20 == 0:
                    print(f"{run_name}: step {i}/{n}, d={(item['distance'] if item else float(distances[i-1])):.2f} AU, section downloads so far={tiles.downloads}, elapsed={time.monotonic()-started:.1f}s")
                    _save_partial(runs, payload, truth, tiles, started, global_stop, peak_payload)
                if item is None:
                    output["skipped"] += 1
                    output["skipped_reasons"]["no_window2_coverage"] = output["skipped_reasons"].get("no_window2_coverage", 0) + 1
                    continue
                if item.get("template") is None:
                    output["skipped"] += 1
                    output["skipped_reasons"]["no_valid_window3_template"] = output["skipped_reasons"].get("no_valid_window3_template", 0) + 1
                    continue
                target_row, template_row = item["target"], item["template"]
                cur = {}
                def get_stamp_for_position(ra, dec, time_arg):
                    difference, detail = tiles.difference_stamp(target_row, template_row, ra, dec)
                    cur["detail"] = detail
                    return difference
                t1 = Time(float(item["t1_mjd"]), format="mjd", scale="utc")
                result = focus_curve(run_ra, run_dec, t0, t1, [item["distance"]],
                                     get_stamp_for_position, orbit=orbit)
                if not result:
                    output["skipped"] += 1
                    output["skipped_reasons"]["insufficient_unflagged_pixels"] = output["skipped_reasons"].get("insufficient_unflagged_pixels", 0) + 1
                else:
                    step = result[0]
                    step["target_obs_id"] = target_row.get("obs_id")
                    step["target_collection"] = target_row.get("obs_collection")
                    step["target_t1_mjd"] = float(item["t1_mjd"])
                    step["target_detector"] = re.search(r"D([1-3])_spx_", target_row["access_url"]).group(1)
                    step["template_obs_id"] = template_row.get("obs_id")
                    step["template_collection"] = template_row.get("obs_collection")
                    step["template_detector"] = re.search(r"D([1-3])_spx_", template_row["access_url"]).group(1)
                    step["template_neptune_sep_deg"] = item["template_neptune_sep_deg"]
                    output["steps"].append(step)
                    for row, role in ((target_row, "target"), (template_row, "template")):
                        output["exposures"][row["access_url"]] = {"role": role, "obs_id": row.get("obs_id"),
                                                                      "collection": row.get("obs_collection"),
                                                                      "detector": re.search(r"D([1-3])_spx_", row["access_url"]).group(1),
                                                                      "access_url": row["access_url"]}
                    if run_name == "circular" and (peak_payload is None or step["snr"] > peak_payload[3]["snr"]):
                        a, b, diff, ratio, _, _ = cur["detail"]
                        if diff is not None:
                            peak_payload = (a, b, diff, {"run": run_name, "distance_au": step["distance_au"],
                                                        "snr": step["snr"], "template_scale": ratio})
    except StopRun as exc:
        global_stop = str(exc)
        print("STOP:", global_stop)
    except Exception as exc:
        global_stop = f"{type(exc).__name__}: {exc}"
        print("GRID ERROR (exact):", repr(exc))
    finally:
        _save_partial(runs, payload, truth, tiles, started, global_stop, peak_payload)


def _save_partial(runs, payload, truth, tiles, started, stop_reason, peak_payload):
    payload_runs = {}
    for name, run in runs.items():
        run["summary"] = _summary(run["steps"], truth)
        run["steps_used"] = len(run["steps"])
        payload_runs[name] = {**run, "exposures": list(run["exposures"].values())}
    payload["runs"] = payload_runs
    payload["skipped_count"] = sum(run["skipped"] for run in runs.values())
    payload["sections_downloaded"] = tiles.downloads
    payload["section_cache_count_total"] = len({p.resolve() for p in tiles.section_dir.glob("*.fits")})
    payload["sections_served_by_source"] = tiles.source_counts.copy()
    payload["source_errors"] = tiles.source_errors
    payload["elapsed_seconds"] = round(time.monotonic() - started, 1)
    payload["stopped_reason"] = stop_reason
    _write_json(payload)
    _plot_outputs(runs, truth, peak_payload)


if __name__ == "__main__":
    prior_path = OUT / "focus_neptune.json"
    if prior_path.exists() and (OUT / "identity_check.png").exists():
        prior = json.loads(prior_path.read_text())
        with (POC / "coverage_neptune.csv").open(newline="") as f:
            reference = next(r for r in csv.DictReader(f) if r["window_id"] == "1"
                             and r.get("obs_id") == "2025W25_2A_0500_1"
                             and re.search(r"D1_spx_", r.get("access_url", "")))
        eph0 = {"ra_deg": prior["ra0_deg"], "dec_deg": prior["dec0_deg"],
                "r_au": prior["truth_r_au"], "source": prior["ephemeris_source"]}
        t0 = Time(prior["t0_utc"], scale="utc")
        identity_summary = {"same_position_source_remains": False,
                            "window1_peak_within_3px_mjysr": 77.78388214111328,
                            "window3_peak_within_3px_mjysr": 0.42944443225860596,
                            "window3_robust_annulus_sigma": 0.9089258498384737,
                            "source_gone": True}
        print("Reusing the completed sanity and identity checks from poc/out; no IRSA requests for those stamps.")
        print("Identity peaks within 3 px:", identity_summary["window1_peak_within_3px_mjysr"],
              "(window 1) vs", identity_summary["window3_peak_within_3px_mjysr"], "(window 3); source gone")
        run_grid(reference, eph0, t0, identity_summary)
    else:
        result = sanity_check()
        same_source = identity_check(*result[:2], result[3], result[4])
        if same_source:
            print("STOP: same compact source is present in window 3; do not run the distance grid.")
        else:
            print("Identity check clear; continue with the distance grid.")
            run_grid(result[0], result[1], result[2])
