"""Focus Curve: signal at the crosshair as a function of assumed distance.

For each trial distance d we predict where an object seen at (ra0, dec0) at t0
would be at t1, get an image stamp centred there, and measure the best aperture
S/N within `search_radius_px` of the crosshair. A real object gives a single
peak at its true distance; an empty-sky control gives no peak.

IMPORTANT: `get_stamp` must return a STAR-SUBTRACTED stamp (epoch t1 minus a
frame of the same sky at another epoch, same wavelength if possible). On raw
stamps random field stars inside the 20 px window produce false peaks — the
empty-sky control fails. Static stars cancel in the difference; a mover does not.

`get_stamp(ra_deg, dec_deg, time) -> 2-D numpy array or None` is injected so the
same code runs on real SPHEREx cutouts (wrap io.fetch_cutout + read_frame) and on
synthetic fixtures (tests). Output rows match CONTRACT.md `dial.steps`.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
from astropy.time import Time

from .geometry import predict_radec, ang_sep_deg


def aperture_snr_map(stamp: np.ndarray, r_ap: float = 2.5, search_radius_px: float = 20):
    """Return (best_snr, offset_px) for the brightest aperture within the search radius."""
    img = np.nan_to_num(np.asarray(stamp, dtype=float), nan=np.nanmedian(stamp))
    ny, nx = img.shape
    cy, cx = (ny - 1) / 2, (nx - 1) / 2
    bkg = np.median(img)
    noise = 1.4826 * np.median(np.abs(img - bkg)) or np.std(img) or 1.0
    yy, xx = np.mgrid[-int(np.ceil(r_ap)):int(np.ceil(r_ap)) + 1, -int(np.ceil(r_ap)):int(np.ceil(r_ap)) + 1]
    kern = (xx ** 2 + yy ** 2 <= r_ap ** 2).astype(float)
    npix = kern.sum()
    # aperture sum via FFT-free convolution (small kernel)
    from numpy.lib.stride_tricks import sliding_window_view
    k = kern.shape[0]
    pad = k // 2
    win = sliding_window_view(np.pad(img - bkg, pad, mode="edge"), (k, k))
    flux = np.einsum("ijkl,kl->ij", win, kern)
    snr = flux / (noise * np.sqrt(npix))
    Y, X = np.mgrid[0:ny, 0:nx]
    r = np.hypot(Y - cy, X - cx)
    snr_in = np.where(r <= search_radius_px, snr, -np.inf)
    iy, ix = np.unravel_index(np.argmax(snr_in), snr_in.shape)
    return float(snr_in[iy, ix]), float(r[iy, ix])


def dial_grid(dmin_au: float = 15, dmax_au: float = 1000, step_px: float = 15,
              k_px_au: float = 72600.0) -> np.ndarray:
    """Distance grid uniform in 1/d (parallax ∝ 1/d) so the predicted position moves
    at most `step_px` between steps. k_px_au ≈ half-year shift [px] × d [AU]
    (≈ 248′ × 30 AU at quadrature / 6.15″). A grid uniform in d skips the target
    at small d: near 30 AU one AU is ~80 px of shift.
    """
    inv = np.arange(1 / dmax_au, 1 / dmin_au + 1e-12, step_px / k_px_au)
    return np.sort(1 / inv)


def focus_curve(ra0: float, dec0: float, t0: Time, t1: Time, distances_au,
                get_stamp: Callable[[float, float, Time], np.ndarray | None],
                search_radius_px: float = 20, orbit: str = "circular") -> list[dict]:
    steps = []
    for d in distances_au:
        ra, dec = predict_radec(ra0, dec0, t0, float(d), t1, orbit)[0]
        if np.isnan(ra):
            continue
        stamp = get_stamp(ra, dec, t1)
        if stamp is None:
            continue
        snr, off = aperture_snr_map(stamp, search_radius_px=search_radius_px)
        steps.append({"distance_au": round(float(d), 2),
                      "pred": {"ra_deg": round(float(ra), 6), "dec_deg": round(float(dec), 6)},
                      "snr": round(snr, 2), "offset_px": round(off, 2)})
    return steps


def summarize(steps: list[dict], truth_au: float | None = None) -> dict:
    """Peak distance, peak/median ratio and (if truth given) % error — PoC B success metrics."""
    snr = np.array([s["snr"] for s in steps])
    d = np.array([s["distance_au"] for s in steps])
    i = int(np.argmax(snr))
    med = float(np.median(snr))
    out = {"peak_distance_au": float(d[i]), "peak_snr": float(snr[i]), "median_snr": med,
           "peak_over_median": float(snr[i] / med) if med > 0 else float("inf")}
    if truth_au:
        out["err_pct"] = 100 * (d[i] - truth_au) / truth_au
        out["pass"] = abs(out["err_pct"]) <= 15 and out["peak_over_median"] >= 3
    return out
