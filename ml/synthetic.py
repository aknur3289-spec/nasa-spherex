"""Labelled synthetic scenes for tests and the demo queue. Everything here is SYNTHETIC.

Each scene is a science/reference pair of the same star field. The science frame gets real
movers (point sources absent from the reference) and several artefact types. The pair is then
passed through the unchanged blind detector (`blind_mover.difference` + `detect`), so the
candidates have survived the same cuts as on real data. Candidates are labelled by matching
them to what was injected.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from astropy.wcs import WCS

from ml.blind import bm
from ml.features import extract, stamps

SHAPE = (98, 97)           # real Neptune cutouts are ~97 x 98 px
PIX_DEG = 6.15 / 3600
MATCH_PX = 2.0
REAL_KINDS = ("mover",)
BOGUS_KINDS = ("cosmic", "dipole", "ghost", "streak", "noise")


def _wcs(ra=10.0, dec=0.0) -> WCS:
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [SHAPE[1] / 2, SHAPE[0] / 2]
    w.wcs.cdelt = [-PIX_DEG, PIX_DEG]
    return w


def _gauss(x0, y0, peak, fwhm, shape=SHAPE):
    yy, xx = np.indices(shape)
    s = fwhm / 2.3548
    return peak * np.exp(-((xx - x0) ** 2 + (yy - y0) ** 2) / (2 * s * s))


def make_scene(rng: np.random.Generator, n_movers: int = 3, n_artefacts: int = 6) -> tuple[dict, dict, list[dict]]:
    """Return (sci, ref, truth) in the dict format of `blind_mover.load()`."""
    sigma = 1.0
    fwhm = rng.uniform(1.1, 1.6)
    wcs = _wcs(rng.uniform(0, 360), rng.uniform(-30, 30))
    stars = np.zeros(SHAPE)
    star_xy = []
    for _ in range(rng.integers(15, 40)):                       # shared static stars
        x, y = rng.uniform(3, SHAPE[1] - 3), rng.uniform(3, SHAPE[0] - 3)
        stars += _gauss(x, y, sigma * 10 ** rng.uniform(0.7, 3.0), fwhm)
        star_xy.append((x, y))
    sky = 0.3 * np.sin(np.indices(SHAPE)[1] / 30.0)            # smooth background
    ref_img = stars + sky + rng.normal(0, sigma, SHAPE)
    sci_img = stars * rng.uniform(0.97, 1.03) + sky + rng.normal(0, sigma, SHAPE)
    truth = []

    def free_xy(margin=8):
        for _ in range(50):
            x, y = rng.uniform(margin, SHAPE[1] - margin), rng.uniform(margin, SHAPE[0] - margin)
            if all(np.hypot(x - sx, y - sy) > 4 for sx, sy in star_xy):
                return x, y
        return x, y

    for _ in range(n_movers):
        x, y = free_xy()
        sci_img += _gauss(x, y, sigma * 10 ** rng.uniform(np.log10(6), np.log10(60)), fwhm)
        truth.append({"x": x, "y": y, "kind": "mover"})
    for _ in range(n_artefacts):
        kind = rng.choice(["cosmic", "dipole", "ghost", "streak"])
        if kind == "cosmic":                                    # 1-2 hot pixels, very sharp
            x, y = free_xy()
            xi, yi = int(x), int(y)
            sci_img[yi, xi] += sigma * rng.uniform(15, 200)
            if rng.random() < 0.5:
                sci_img[yi, xi + 1] += sigma * rng.uniform(5, 60)
        elif kind == "dipole" and star_xy:                       # misregistered bright star
            i = rng.integers(len(star_xy))
            x, y = star_xy[i]
            peak = sigma * 10 ** rng.uniform(2.0, 3.0)
            dx, dy = rng.normal(0, 0.8, 2)
            sci_img += _gauss(x + dx, y + dy, peak, fwhm) - _gauss(x, y, peak, fwhm)
            x, y = x + dx, y + dy
        elif kind == "ghost":                                   # broad faint blob
            x, y = free_xy()
            sci_img += _gauss(x, y, sigma * rng.uniform(4, 12), rng.uniform(3.5, 6.0))
        else:                                                   # short satellite / CR streak
            x, y = free_xy(12)
            ang, L = rng.uniform(0, np.pi), rng.uniform(6, 14)
            for t in np.linspace(-L / 2, L / 2, int(L * 3)):
                sci_img += _gauss(x + t * np.cos(ang), y + t * np.sin(ang), sigma * rng.uniform(3, 8) / 3, 0.9)
        truth.append({"x": x, "y": y, "kind": str(kind)})

    var = np.full(SHAPE, sigma ** 2)
    bad = np.zeros(SHAPE, bool)
    for _ in range(rng.integers(0, 4)):                         # a few masked pixels
        bad[rng.integers(SHAPE[0]), rng.integers(SHAPE[1])] = True
    sci = {"img": sci_img, "var": var.copy(), "bad": bad, "wcs": wcs, "mjd": 61000.0, "path": "synthetic"}
    ref = {"img": ref_img, "var": var.copy(), "bad": bad.copy(), "wcs": wcs, "mjd": 60800.0, "path": "synthetic"}
    return sci, ref, truth


def label_candidates(cands: list[dict], truth: list[dict]) -> list[str]:
    """Nearest injected object within MATCH_PX gives the kind; otherwise 'noise'."""
    kinds = []
    for c in cands:
        best, kind = MATCH_PX, "noise"
        for t in truth:
            r = np.hypot(c["x"] - t["x"], c["y"] - t["y"])
            if r < best:
                best, kind = r, t["kind"]
        kinds.append(kind)
    return kinds


def build(n_scenes: int = 200, seed: int = 0, with_stamps: bool = False) -> tuple[pd.DataFrame, dict | None]:
    """Synthetic candidate table (one row per detection) and optional stamps keyed by row index."""
    rng = np.random.default_rng(seed)
    rows, st = [], {}
    for s in range(n_scenes):
        sci, ref, truth = make_scene(rng)
        d = bm.difference(sci, ref)
        if d is None:
            continue
        cands = bm.detect(d, sci["wcs"])
        for c, kind in zip(cands, label_candidates(cands, truth)):
            f = extract(d, c["x"], c["y"])
            i = len(rows)
            rows.append({**f, "x": c["x"], "y": c["y"], "ra": c["ra"], "dec": c["dec"],
                         "kind": kind, "label": int(kind in REAL_KINDS), "group": f"syn{s:04d}",
                         "source": "synthetic"})
            if with_stamps:
                st[i] = stamps(d, c["x"], c["y"])
    return pd.DataFrame(rows), (st if with_stamps else None)
