"""Blind moving-object search on SPHEREx cutouts, then distance from the detections.

The detector, the linking and the distance fit never read JPL Horizons. Ephemerides are
loaded only by `score()` at the end, to grade what the blind steps produced.

Steps
1. Difference image: science (IMAGE - ZODI) minus a reference of the same sky taken at
   another time, reprojected onto the science grid, flux-scaled, noise from VARIANCE.
2. Detection: local maxima of the normalised difference, z > Z_MIN, with real new flux.
3. Linking: candidates from different exposures that follow one smooth track.
4. Distance: circular-orbit model anchored on the June track, fitted to the December track.

Run: python3 poc/blind_mover.py   (offline; reads data/raw and data/meta)
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from astropy import units as u
from astropy.coordinates import SkyCoord, get_body_barycentric
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS, FITSFixedWarning
from reproject import reproject_interp
from scipy import ndimage

warnings.simplefilter("ignore", FITSFixedWarning)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from spx.frame import BAD_BITS, _named_mask  # noqa: E402

# The SPHEREx pipeline flags a moving source as OUTLIER/TRANSIENT (it differs from the other
# samples). For a mover search those flags are signal, not damage, so they are kept.
MOVER_BAD_BITS = tuple(b for b in BAD_BITS if b not in ("OUTLIER", "TRANSIENT"))
MASK_BITS = MOVER_BAD_BITS

OUT = ROOT / "data" / "meta" / "blind"
PIX = 6.15            # arcsec per SPHEREx pixel
Z_MIN = 5.0           # detection threshold in normalised difference
NEW_FLUX = 0.5        # at least half the peak flux must be absent from the reference
EDGE = 4              # px kept clear of the frame / overlap edge
MAX_DLAM = 0.10       # reference wavelength mismatch allowed (fraction)
JUNE_MIN_DT = 4.0     # days between a June science frame and its June reference
GM_SUN = 2.959122082855911e-4  # AU^3 / day^2
EPS = np.deg2rad(23.4392911)
Z_ECL = np.array([0.0, -np.sin(EPS), np.cos(EPS)])  # ecliptic pole in ICRS


# ---------------------------------------------------------------- frames
def load(path: Path) -> dict:
    with fits.open(path, memmap=False) as h:
        img = h["IMAGE"].data.astype(float) - h["ZODI"].data.astype(float)
        var = h["VARIANCE"].data.astype(float)
        bad = _named_mask(h["FLAGS"].data, h["FLAGS"].header, MASK_BITS) | ~np.isfinite(img) | ~np.isfinite(var) | (var <= 0)
        wcs = WCS(h["IMAGE"].header)
        mjd = float(h["IMAGE"].header["MJD-OBS"])
    return {"img": img, "var": var, "bad": bad, "wcs": wcs, "mjd": mjd, "path": str(path)}


def difference(sci: dict, ref: dict) -> dict | None:
    shape = sci["img"].shape
    rimg, cover = reproject_interp((np.where(ref["bad"], np.nan, ref["img"]), ref["wcs"]), sci["wcs"], shape_out=shape)
    rvar, _ = reproject_interp((np.where(ref["bad"], np.nan, ref["var"]), ref["wcs"]), sci["wcs"], shape_out=shape)
    ok = (~sci["bad"]) & np.isfinite(rimg) & np.isfinite(rvar) & (cover > 0.99)
    ok = ndimage.binary_erosion(ok, iterations=1)
    if ok.sum() < 0.25 * ok.size:
        return None
    s_img = sci["img"] - np.median(sci["img"][ok])
    r_img = rimg - np.median(rimg[ok])
    rnoise = 1.4826 * np.median(np.abs(r_img[ok]))
    bright = ok & (r_img > 10 * rnoise)
    scale = float(np.median(s_img[bright] / r_img[bright])) if bright.sum() >= 5 else 1.0
    if not (0.2 < scale < 5):
        scale = 1.0
    diff = s_img - scale * r_img
    sigma = np.sqrt(sci["var"] + scale ** 2 * np.where(np.isfinite(rvar), rvar, np.inf))
    z = np.where(ok, diff / sigma, 0.0)
    k = 1.4826 * np.median(np.abs(z[ok]))  # correct VARIANCE to the real scatter
    z = z / k if k > 0 else z
    return {"z": z, "ok": ok, "diff": diff, "sci": s_img, "ref": scale * r_img, "scale": scale, "k": float(k),
            "valid_frac": float(ok.mean())}


def detect(d: dict, wcs: WCS) -> list[dict]:
    z, ok = d["z"], d["ok"]
    # keep clear of the frame / overlap edge only; small masked holes inside (saturated cores) are allowed
    inner = ndimage.binary_erosion(ndimage.binary_fill_holes(ok), iterations=EDGE)
    peaks = (z == ndimage.maximum_filter(z, size=5)) & (z > Z_MIN) & inner & ok
    support = ndimage.uniform_filter((z > 2).astype(float), size=3) * 9
    out = []
    yy, xx = np.indices(z.shape)
    for y, x in zip(*np.nonzero(peaks)):
        if support[y, x] < 3:          # isolated hot pixel
            continue
        sci_peak, ref_peak = d["sci"][y, x], d["ref"][y, x]
        if sci_peak <= 0 or (sci_peak - ref_peak) < NEW_FLUX * sci_peak:
            continue                   # flux mostly present in the reference: residual of a static star
        box = (abs(yy - y) <= 2) & (abs(xx - x) <= 2) & ok
        w = np.where(box, np.maximum(d["diff"], 0), 0)
        cx, cy = (float((xx * w).sum() / w.sum()), float((yy * w).sum() / w.sum())) if w.sum() > 0 else (float(x), float(y))
        ra, dec = wcs.pixel_to_world_values(cx, cy)
        out.append({"x": cx, "y": cy, "ra": float(ra), "dec": float(dec), "z": float(z[y, x]),
                    "new_flux_frac": float((sci_peak - ref_peak) / sci_peak)})
    return sorted(out, key=lambda c: -c["z"])


# ---------------------------------------------------------------- linking
def _tangent(ra, dec, ra0, dec0):
    c = SkyCoord(ra * u.deg, dec * u.deg).transform_to(SkyCoord(ra0 * u.deg, dec0 * u.deg).skyoffset_frame())
    return c.lon.arcsec, c.lat.arcsec


def link(cands: pd.DataFrame, tol_px: float = 3.0, max_rate_deg_day: float = 0.5, min_span_px: float = 3.0) -> pd.DataFrame | None:
    """Best smooth track through candidates of different exposures (no ephemeris used)."""
    if cands.empty:
        return None
    ra0, dec0 = cands.ra.median(), cands.dec.median()
    x, y = _tangent(cands.ra.values, cands.dec.values, ra0, dec0)
    c = cands.assign(tx=x, ty=y).reset_index(drop=True)
    t, tol = c.mjd.values, tol_px * PIX
    best, best_key = None, (0, 0.0)
    for i in range(len(c)):
        for j in range(len(c)):
            dt = t[j] - t[i]
            if dt < 1.0:
                continue
            vx, vy = (c.tx[j] - c.tx[i]) / dt, (c.ty[j] - c.ty[i]) / dt
            if np.hypot(vx, vy) > max_rate_deg_day * 3600:
                continue
            idx = _members(c, lambda tt: (c.tx[i] + vx * (tt - t[i]), c.ty[i] + vy * (tt - t[i])), tol)
            for _ in range(2):                        # refine with a quadratic track
                if len(idx) < 4:
                    break
                m = c.loc[idx]
                px, py = np.polyfit(m.mjd, m.tx, 2), np.polyfit(m.mjd, m.ty, 2)
                idx = _members(c, lambda tt: (np.polyval(px, tt), np.polyval(py, tt)), tol)
            m = c.loc[idx]
            span = np.hypot(m.tx.max() - m.tx.min(), m.ty.max() - m.ty.min()) / PIX
            if span < min_span_px:                # a source that stays put is not a moving object
                continue
            key = (len(set(m.obs_id)), float(m.z.sum()))
            if key > best_key:
                best, best_key = idx, key
    return None if best is None else c.loc[best].sort_values("mjd")


def _members(c, model, tol):
    px, py = model(c.mjd.values)
    r = np.hypot(c.tx.values - px, c.ty.values - py)
    sel = pd.DataFrame({"obs": c.obs_id, "r": r, "i": c.index})[r < tol]
    return list(sel.sort_values("r").drop_duplicates("obs").i)


STATIC_SPAN_PX = 5.0   # a track that moves less than this over the window is a static source
GHOST_STD_PX = 2.0     # a track that keeps a fixed offset from a brighter mover is its optical ghost
COMPANION_PX = 50.0    # ... or stays within this many px of it,
COMPANION_SHARE = 0.8  # in at least this share of its exposures


def all_tracks(cands: pd.DataFrame, min_points: int = 4, max_tracks: int = 8) -> list[dict]:
    """Extract tracks one by one and label them: mover, static, or ghost of a mover."""
    rest, out = cands.copy(), []
    while len(out) < max_tracks:
        tr = link(rest)
        if tr is None or len(tr) < min_points:
            break
        span = float(np.hypot(tr.tx.max() - tr.tx.min(), tr.ty.max() - tr.ty.min()) / PIX)
        out.append({"track": tr, "points": int(len(tr)), "span_px": span, "median_z": float(tr.z.median()),
                    "label": "static" if span < STATIC_SPAN_PX else "mover"})
        key = tr[["obs_id", "x", "y"]].apply(tuple, axis=1)
        rest = rest[~rest[["obs_id", "x", "y"]].apply(tuple, axis=1).isin(set(key))]
    movers = [t for t in out if t["label"] == "mover"]
    for t in movers:                       # ghost test against every brighter mover
        for primary in movers:
            if primary is t or primary["median_z"] <= t["median_z"]:
                continue
            m = t["track"].merge(primary["track"], on="obs_id", suffixes=("", "_p"))
            if len(m) >= 3:
                # optical ghosts sit at a fixed offset on the detector (cutouts are detector sub-arrays),
                # not on the sky, because the detector orientation changes between exposures
                off = np.c_[m.x - m.x_p, m.y - m.y_p]
                if np.hypot(*off.std(axis=0)) < GHOST_STD_PX:
                    t["label"] = "ghost"
                    t["ghost_offset_px"] = float(np.hypot(*off.mean(axis=0)))
                elif (len(m) >= COMPANION_SHARE * len(t["track"])
                      and np.median(np.hypot(m.x - m.x_p, m.y - m.y_p)) < COMPANION_PX):
                    # only seen in the bright mover's exposures, always close to it: PSF wings,
                    # ghosts on another detector, or star residuals the bright source drags along
                    t["label"] = "companion"
                    t["companion_offset_px"] = float(np.median(np.hypot(m.x - m.x_p, m.y - m.y_p)))
    return out


# ---------------------------------------------------------------- distance
def _earth(mjd):
    t = Time(mjd, format="mjd", scale="tdb")
    e = get_body_barycentric("earth", t).xyz.to_value(u.AU)
    s = get_body_barycentric("sun", t).xyz.to_value(u.AU)
    return (e - s).T            # heliocentric Earth, ICRS axes


def _unit(ra, dec):
    ra, dec = np.deg2rad(ra), np.deg2rad(dec)
    return np.array([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)])


def predict(ra0, dec0, t0, r, tilt_deg, t1):
    """Circular heliocentric orbit of radius r through the direction (ra0, dec0) seen at t0.

    Prograde; orbit pole = ecliptic pole projected perpendicular to the position, then rotated
    by tilt_deg about the position vector. Returns predicted (ra, dec) at times t1.
    """
    E0 = _earth(np.atleast_1d(t0))[0]
    uvec = _unit(ra0, dec0)
    b = uvec @ E0
    disc = b * b - (E0 @ E0 - r * r)
    if disc < 0:
        return None
    P0 = E0 + uvec * (-b + np.sqrt(disc))
    p = P0 / np.linalg.norm(P0)
    k = Z_ECL - (Z_ECL @ p) * p
    k /= np.linalg.norm(k)
    a = np.deg2rad(tilt_deg)                     # Rodrigues rotation of k about p
    k = k * np.cos(a) + np.cross(p, k) * np.sin(a)
    n = np.sqrt(GM_SUN / r ** 3)
    th = n * (np.atleast_1d(t1) - t0)
    P = (np.outer(np.cos(th), P0) + np.outer(np.sin(th), np.cross(k, P0)))
    g = P - _earth(np.atleast_1d(t1))
    g /= np.linalg.norm(g, axis=1)[:, None]
    return np.rad2deg(np.arctan2(g[:, 1], g[:, 0])) % 360, np.rad2deg(np.arcsin(g[:, 2]))


def miss_arcsec(anchor, targets, r, tilt):
    pr = predict(anchor["ra"], anchor["dec"], anchor["mjd"], r, tilt, targets.mjd.values)
    if pr is None:
        return np.inf
    sep = SkyCoord(pr[0] * u.deg, pr[1] * u.deg).separation(SkyCoord(targets.ra.values * u.deg, targets.dec.values * u.deg))
    return float(np.sqrt(np.mean(sep.arcsec ** 2)))


def fit_distance(anchor, targets, r_grid, tilts):
    grid = np.array([[miss_arcsec(anchor, targets, r, a) for a in tilts] for r in r_grid])
    i, j = np.unravel_index(np.argmin(grid), grid.shape)
    return {"r_au": float(r_grid[i]), "tilt_deg": float(tilts[j]), "miss_arcsec": float(grid[i, j]),
            "profile": grid.min(axis=1)}


# ---------------------------------------------------------------- experiment
def neptune_pairs():
    e = pd.read_csv(ROOT / "data/meta/neptune/epochs.csv")
    e = e[e.status == "ok"].copy()
    tpl = pd.read_csv(ROOT / "data/meta/neptune/templates.csv")
    tpl["dlam"] = tpl.delta_lambda_um / tpl.science_wavelength_um
    pairs = []
    for _, s in e[e.window_id == 2].iterrows():
        opts = tpl[tpl.science_obs_id == s.obs_id].sort_values("dlam")
        if len(opts) and opts.iloc[0].dlam <= MAX_DLAM:
            o = opts.iloc[0]
            pairs.append((s, ROOT / o.template_local_path, o.template_obs_id, float(o.dlam)))
    june = e[e.window_id == 1]
    for _, s in june.iterrows():
        cands = june[(abs(june.mjd - s.mjd) >= JUNE_MIN_DT)].copy()
        cands["dlam"] = abs(cands.wavelength_um - s.wavelength_um) / ((cands.wavelength_um + s.wavelength_um) / 2)
        cands = cands[cands.dlam <= MAX_DLAM].copy()
        # geometry only: overlap of the two cutout footprints (centre distance), never the ephemeris
        sc = SkyCoord(s.eph_ra * u.deg, s.eph_dec * u.deg)  # == cutout centre requested at download
        cands["sep_px"] = sc.separation(SkyCoord(cands.eph_ra.values * u.deg, cands.eph_dec.values * u.deg)).arcsec / PIX
        cands = cands[cands.sep_px < 40].sort_values(["sep_px", "dlam"])
        if len(cands):
            o = cands.iloc[0]
            pairs.append((s, ROOT / o.local_path, o.obs_id, float(o.dlam)))
    return pairs


def run_neptune():
    rows, cand_rows = [], []
    for s, ref_path, ref_id, dlam in neptune_pairs():
        sci = load(ROOT / s.local_path)
        d = difference(sci, load(ref_path))
        info = {"obs_id": s.obs_id, "window": int(s.window_id), "mjd": sci["mjd"], "detector": int(s.detector),
                "ref_obs_id": ref_id, "dlam": dlam, "n_cand": 0, "valid_frac": 0.0}
        if d is not None:
            cands = detect(d, sci["wcs"])
            info.update(n_cand=len(cands), valid_frac=d["valid_frac"], scale=d["scale"], noise_k=d["k"])
            for rank, c in enumerate(cands, 1):
                cand_rows.append({**c, "rank": rank, "obs_id": s.obs_id, "window": int(s.window_id), "mjd": sci["mjd"]})
        rows.append(info)
    return pd.DataFrame(rows), pd.DataFrame(cand_rows)


def run_controls():
    """Same detector on Honest Blink strict pairs of fields with no known planet."""
    out, ctl_cands = [], []
    for field in ("m101", "nep", "ecl"):
        ep = pd.read_csv(ROOT / f"data/meta/{field}/epochs.csv").set_index("frame_id")
        pr = pd.read_csv(ROOT / f"data/meta/{field}/pairs.csv")
        pr = pr[pr.trust == "high"]
        for _, p in pr.iterrows():
            a, b = ep.loc[p.a], ep.loc[p.b]
            for s, r in ((a, b), (b, a)):
                sp, rp = ROOT / s.local_path, ROOT / r.local_path
                if not (sp.is_file() and rp.is_file()):
                    continue
                sci = load(sp)
                d = difference(sci, load(rp))
                if d is None:
                    continue
                c = detect(d, sci["wcs"])
                for x in c:
                    ctl_cands.append({**x, "field": field, "obs_id": s.name + "-" + r.name, "mjd": sci["mjd"]})
                out.append({"field": field, "sci": s.name, "ref": r.name, "n_cand": len(c),
                            "valid_area_deg2": float(d["ok"].sum() * (PIX / 3600) ** 2),
                            "max_z": max([x["z"] for x in c], default=None)})
    cc = pd.DataFrame(ctl_cands)
    tracks = []
    for field in ("m101", "nep", "ecl"):
        sub = cc[cc.field == field] if len(cc) else cc
        for t in (all_tracks(sub) if len(sub) else []):
            tracks.append({"field": field, **{k: v for k, v in t.items() if k != "track"}})
    return pd.DataFrame(out), tracks


def score(per, cands, tracks):
    """Only here: compare with JPL Horizons."""
    raw = pd.read_csv(ROOT / "data/meta/neptune/raw_index.csv")
    eph = pd.read_csv(ROOT / "data/meta/neptune/epochs.csv").set_index("obs_id")
    per = per.copy()
    hit, rank = [], []
    for _, r in per.iterrows():
        c = cands[cands.obs_id == r.obs_id] if len(cands) else cands
        if c.empty:
            hit.append(False); rank.append(None); continue
        sep = SkyCoord(c.ra.values * u.deg, c.dec.values * u.deg).separation(
            SkyCoord(eph.loc[r.obs_id, "eph_ra"] * u.deg, eph.loc[r.obs_id, "eph_dec"] * u.deg)).arcsec
        m = sep < 2 * PIX
        hit.append(bool(m.any())); rank.append(int(c["rank"].values[m].min()) if m.any() else None)
    per["neptune_found"], per["neptune_rank"] = hit, rank
    track_ok = {}
    for w, tr in tracks.items():
        sep = SkyCoord(tr.ra.values * u.deg, tr.dec.values * u.deg).separation(
            SkyCoord(eph.loc[tr.obs_id, "eph_ra"].values * u.deg, eph.loc[tr.obs_id, "eph_dec"].values * u.deg)).arcsec
        track_ok[w] = {"n_points": int(len(tr)), "median_offset_arcsec": float(np.median(sep)),
                       "max_offset_arcsec": float(np.max(sep))}
    return per, track_ok, raw


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    per, cands = run_neptune()
    cands.to_csv(OUT / "neptune_candidates.csv", index=False)
    tracks, track_table = {}, []
    for w in (1, 2):
        found = all_tracks(cands[cands.window == w]) if len(cands) else []
        for n, t in enumerate(found, 1):
            t["track"].to_csv(OUT / f"track_window{w}_{n}_{t['label']}.csv", index=False)
            track_table.append({"window": w, "n": n, **{k: v for k, v in t.items() if k != "track"}})
        movers = [t for t in found if t["label"] == "mover"]
        if movers:                      # the strongest real mover is the one we follow
            tracks[w] = max(movers, key=lambda t: (t["points"], t["median_z"]))["track"]
            tracks[w].to_csv(OUT / f"track_window{w}.csv", index=False)
    result = {"per_window": {}, "tracks": track_table}
    if 1 in tracks and 2 in tracks:
        june, dec = tracks[1], tracks[2]
        mid = june.iloc[len(june) // 2]
        anchor = {"ra": float(mid.ra), "dec": float(mid.dec), "mjd": float(mid.mjd)}
        r_grid = np.geomspace(5, 300, 600)
        tilts = np.arange(-20, 20.1, 2.0)
        fit = fit_distance(anchor, dec, r_grid, tilts)
        fine = np.linspace(fit["r_au"] * 0.97, fit["r_au"] * 1.03, 121)
        fit2 = fit_distance(anchor, dec, fine, np.arange(fit["tilt_deg"] - 2, fit["tilt_deg"] + 2.01, 0.25))
        rng = np.random.default_rng(1)
        boot = []
        for _ in range(60):                      # resample detections, add 0.3 px centroid noise
            jj = june.sample(len(june), replace=True, random_state=rng.integers(1e9))
            dd = dec.sample(len(dec), replace=True, random_state=rng.integers(1e9))
            a = jj.iloc[rng.integers(len(jj))]
            jitter = rng.normal(0, 0.3 * PIX / 3600, 2)
            anc = {"ra": float(a.ra) + jitter[0] / np.cos(np.deg2rad(a.dec)), "dec": float(a.dec) + jitter[1], "mjd": float(a.mjd)}
            f = fit_distance(anc, dd, np.linspace(fit2["r_au"] * 0.95, fit2["r_au"] * 1.05, 81), np.arange(-6, 6.1, 1.0))
            boot.append(f["r_au"])
        result["distance"] = {"anchor": anchor, "r_au": fit2["r_au"], "tilt_deg": fit2["tilt_deg"],
                              "rms_miss_arcsec": fit2["miss_arcsec"], "boot_median": float(np.median(boot)),
                              "boot_std": float(np.std(boot)), "boot_p16_p84": [float(np.percentile(boot, 16)), float(np.percentile(boot, 84))]}
        np.savetxt(OUT / "distance_profile.csv", np.c_[r_grid, fit["profile"]], delimiter=",", header="r_au,rms_miss_arcsec", comments="")
    # ------- grading (Horizons used only from here on)
    per, track_ok, raw = score(per, cands, tracks)
    per.to_csv(OUT / "neptune_per_exposure.csv", index=False)
    for w in (1, 2):
        p = per[per.window == w]
        result["per_window"][w] = {"exposures_with_reference": int(len(p)), "neptune_detected": int(p.neptune_found.sum()),
                                   "neptune_rank1": int((p.neptune_rank == 1).sum()),
                                   "other_candidates_total": int(p.n_cand.sum() - p.neptune_found.sum()),
                                   "track": track_ok.get(w)}
    if "distance" in result:
        tr = raw.iloc[(raw.mjd - result["distance"]["anchor"]["mjd"]).abs().argmin()]
        result["distance"]["horizons_r_au_at_anchor"] = float(tr.r_au)
        result["distance"]["horizons_delta_au_at_anchor"] = float(tr.delta_au)
        result["distance"]["error_au"] = result["distance"]["r_au"] - float(tr.r_au)
        result["distance"]["error_pct"] = 100 * result["distance"]["error_au"] / float(tr.r_au)
    ctl, ctl_tracks = run_controls()
    result["control_tracks"] = ctl_tracks
    ctl.to_csv(OUT / "controls.csv", index=False)
    result["controls"] = {f: {"differences": int(len(g)), "candidates": int(g.n_cand.sum()),
                              "per_deg2": float(g.n_cand.sum() / g.valid_area_deg2.sum()),
                              "frames_with_zero": int((g.n_cand == 0).sum())} for f, g in ctl.groupby("field")}
    nep_area = len(per) and float(per.valid_frac.sum() * 97 * 98 * (PIX / 3600) ** 2)
    result["neptune_frames_other_per_deg2"] = float(sum(v["other_candidates_total"] for v in result["per_window"].values()) / nep_area) if nep_area else None
    result["settings"] = {"mask_bits": list(MASK_BITS), "Z_MIN": Z_MIN, "NEW_FLUX": NEW_FLUX, "MAX_DLAM": MAX_DLAM, "JUNE_MIN_DT": JUNE_MIN_DT, "link_tol_px": 3.0}
    (OUT / "summary.json").write_text(json.dumps(result, indent=2, default=lambda o: None))
    print(json.dumps(result, indent=2, default=lambda o: None))


if __name__ == "__main__":
    main()
