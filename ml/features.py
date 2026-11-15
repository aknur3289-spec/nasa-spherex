"""Features and image stamps around one candidate in a difference image.

Input `d` is the dict returned by `blind_mover.difference()`:
  z (normalised difference), ok (valid mask), diff, sci, ref (flux-scaled, reprojected).
All features are cheap, unit-free or in pixels, and need no ephemeris.
"""
from __future__ import annotations

import numpy as np

STAMP_HALF = 10            # stamps are (2*STAMP_HALF+1)^2 = 21 x 21 px
FWHM_GUESS_PX = 1.2        # median SPHEREx PSF FWHM in pixels (docs/BLIND_TEST.md)

FEATURES = [
    "z",                   # peak significance in the difference
    "new_flux_frac",       # share of the science peak that is absent from the reference
    "support_2sig",        # pixels > 2 sigma in the 5x5 box (1 = lone hot pixel)
    "sharpness",           # peak / sum of positive 3x3 flux (1 = single pixel spike)
    "fwhm_px",             # second-moment FWHM of the positive difference blob
    "ellipticity",         # 1 - b/a from second moments (streaks, trails, edges)
    "psf_corr",            # correlation of the 7x7 difference with a Gaussian PSF
    "neg_frac",            # share of 7x7 pixels with z < -3 (dipole = misregistered star)
    "neg_pos_ratio",       # |min z| / max z in the 7x7 box
    "ref_peak_z",          # how bright the reference is here (star residual indicator)
    "ref_bright_dist_px",  # distance to the brightest reference pixel within the stamp
    "bad_frac_stamp",      # masked share of the 21x21 stamp
    "edge_dist_px",        # distance to the nearest invalid pixel
    "z_ring_rms",          # scatter of z in a 4-7 px ring (bad subtraction around the source)
]


def _box(a: np.ndarray, x: int, y: int, h: int, fill: float = np.nan) -> np.ndarray:
    """Square cut of half-size h centred on (x, y), padded with `fill` at the frame edge."""
    out = np.full((2 * h + 1, 2 * h + 1), fill, dtype=float)
    ys, xs = slice(max(0, y - h), min(a.shape[0], y + h + 1)), slice(max(0, x - h), min(a.shape[1], x + h + 1))
    out[ys.start - (y - h): ys.stop - (y - h), xs.start - (x - h): xs.stop - (x - h)] = a[ys, xs]
    return out


def _gauss(h: int, fwhm: float) -> np.ndarray:
    yy, xx = np.mgrid[-h:h + 1, -h:h + 1]
    s = fwhm / 2.3548
    return np.exp(-(xx ** 2 + yy ** 2) / (2 * s * s))


def _moments(img: np.ndarray) -> tuple[float, float]:
    """FWHM (px) and ellipticity from flux-weighted second moments of a positive image."""
    w = np.where(np.isfinite(img), np.maximum(img, 0), 0)
    tot = w.sum()
    if tot <= 0:
        return np.nan, np.nan
    h = img.shape[0] // 2
    yy, xx = np.mgrid[-h:h + 1, -h:h + 1]
    mx, my = (w * xx).sum() / tot, (w * yy).sum() / tot
    cxx = (w * (xx - mx) ** 2).sum() / tot
    cyy = (w * (yy - my) ** 2).sum() / tot
    cxy = (w * (xx - mx) * (yy - my)).sum() / tot
    tr, det = cxx + cyy, cxx * cyy - cxy ** 2
    disc = np.sqrt(max(tr * tr / 4 - det, 0))
    l1, l2 = tr / 2 + disc, max(tr / 2 - disc, 1e-6)
    fwhm = 2.3548 * np.sqrt(np.sqrt(l1 * l2))
    return float(fwhm), float(1 - np.sqrt(l2 / l1))


def extract(d: dict, x: float, y: float, fwhm_px: float = FWHM_GUESS_PX) -> dict:
    """Feature dict for a candidate at pixel (x, y) of difference `d`."""
    xi, yi = int(round(x)), int(round(y))
    z, ok = d["z"], d["ok"]
    zc = float(z[yi, xi])
    sci_p, ref_p = float(d["sci"][yi, xi]), float(d["ref"][yi, xi])

    z5 = _box(z, xi, yi, 2, 0.0)
    z7 = _box(z, xi, yi, 3, 0.0)
    diff3 = _box(d["diff"], xi, yi, 1, 0.0)
    diff7 = _box(d["diff"], xi, yi, 3, 0.0)
    ok21 = _box(ok.astype(float), xi, yi, STAMP_HALF, 0.0)
    ref21 = _box(d["ref"], xi, yi, STAMP_HALF, np.nan)

    pos3 = np.maximum(diff3, 0).sum()
    sharp = float(max(diff3[1, 1], 0) / pos3) if pos3 > 0 else np.nan
    fwhm, ell = _moments(_box(np.where(z > 1, d["diff"], 0), xi, yi, 3, 0.0))

    g = _gauss(3, fwhm_px).ravel()
    v = diff7.ravel()
    psf_corr = float(np.corrcoef(g, v)[0, 1]) if np.std(v) > 0 else 0.0

    # reference brightness, in units of the difference noise
    noise = float(np.nanmedian(np.abs(d["diff"][ok]))) * 1.4826 if ok.any() else np.nan
    ref_z = ref_p / noise if noise and noise > 0 else np.nan
    if np.isfinite(ref21).any():
        ry, rx = np.unravel_index(np.nanargmax(ref21), ref21.shape)
        ref_dist = float(np.hypot(rx - STAMP_HALF, ry - STAMP_HALF))
    else:
        ref_dist = np.nan

    # distance to the nearest invalid pixel (capped at the stamp half-size)
    bad_idx = np.argwhere(ok21 < 0.5)
    edge = float(np.min(np.hypot(*(bad_idx - STAMP_HALF).T))) if len(bad_idx) else float(STAMP_HALF + 1)

    yy, xx = np.mgrid[-7:8, -7:8]
    rr = np.hypot(xx, yy)
    z15 = _box(z, xi, yi, 7, np.nan)
    ring = z15[(rr >= 4) & (rr <= 7) & np.isfinite(z15)]

    return {
        "z": zc,
        "new_flux_frac": float((sci_p - ref_p) / sci_p) if sci_p > 0 else np.nan,
        "support_2sig": float((z5 > 2).sum()),
        "sharpness": sharp,
        "fwhm_px": fwhm,
        "ellipticity": ell,
        "psf_corr": psf_corr,
        "neg_frac": float((z7 < -3).mean()),
        "neg_pos_ratio": float(abs(min(z7.min(), 0)) / max(z7.max(), 1e-6)),
        "ref_peak_z": float(ref_z),
        "ref_bright_dist_px": ref_dist,
        "bad_frac_stamp": float(1 - ok21.mean()),
        "edge_dist_px": edge,
        "z_ring_rms": float(np.std(ring)) if len(ring) else np.nan,
    }


def stamps(d: dict, x: float, y: float, half: int = STAMP_HALF) -> dict[str, np.ndarray]:
    """Science, reference and difference cut-outs (float, NaN outside the frame / masked)."""
    xi, yi = int(round(x)), int(round(y))
    mask = _box(d["ok"].astype(float), xi, yi, half, 0.0) < 0.5
    out = {}
    for k in ("sci", "ref", "diff"):
        s = _box(d[k], xi, yi, half, np.nan)
        s[mask] = np.nan
        out[k] = s.astype(np.float32)
    return out
