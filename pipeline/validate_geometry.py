"""Scientific validation of the parallax model on known planets (no SPHEREx data needed).

For each planet: find a date near quadrature (elongation ~90°, how SPHEREx sees it),
take its true position then and ~182.6 days later, and recover its distance blindly.
Writes docs/validation_geometry.json and prints a table for EXPERIMENTS.md.

Run: python pipeline/validate_geometry.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from astropy.time import Time
from astropy.coordinates import get_body, solar_system_ephemeris
import astropy.units as u

sys.path.insert(0, str(Path(__file__).parent))
from spx.geometry import fit_distance, solar_elongation_deg, ang_sep_deg  # noqa: E402

PIX = 6.15  # arcsec / SPHEREx pixel


def true_radec(body, t):
    with solar_system_ephemeris.set("builtin"):
        c = get_body(body, t)  # GCRS = geocentric, ICRS-aligned axes
        return c.ra.deg, c.dec.deg, c.distance.to(u.AU).value


def quadrature_time(body, start="2025-05-01", days=365):
    ts = Time(start) + np.arange(0, days, 1.0) * u.day
    el = []
    for t in ts:
        ra, dec, _ = true_radec(body, t)
        el.append(solar_elongation_deg(ra, dec, t))
    return ts[int(np.argmin(np.abs(np.array(el) - 90)))]


def helio_dist(body, t):
    with solar_system_ephemeris.set("builtin"):
        from astropy.coordinates import get_body_barycentric
        p = get_body_barycentric(body, t) - get_body_barycentric("sun", t)
        return float(p.norm().to(u.AU).value)


def run(body, t0_iso=None):
    t0 = Time(t0_iso, scale="utc") if t0_iso else quadrature_time(body)
    t1 = t0 + 182.6 * u.day
    ra0, dec0, _ = true_radec(body, t0)
    ra1, dec1, _ = true_radec(body, t1)
    d_true = helio_dist(body, t0)
    d_best, off, grid = fit_distance(ra0, dec0, t0, ra1, dec1, t1)
    d_static, off_s, _ = fit_distance(ra0, dec0, t0, ra1, dec1, t1, orbit="static")
    shift = ang_sep_deg(ra0, dec0, ra1, dec1) * 60
    # distances where the prediction lands within 20 px of the true position
    ok = grid[off < 20 * PIX]
    return {
        "body": body, "t0_utc": t0.isot, "t1_utc": t1.isot,
        "epoch_pair": f"{t0.datetime:%Y-%m-%d} → {t1.datetime:%Y-%m-%d}",
        "elongation_t0_deg": round(solar_elongation_deg(ra0, dec0, t0), 1),
        "shift_arcmin": round(float(shift), 1),
        "d_true_au": round(d_true, 2),
        "d_fit_au": round(d_best, 2),
        "err_pct": round(100 * (d_best - d_true) / d_true, 1),
        "residual_arcsec": round(float(np.nanmin(off)), 1),
        "d_fit_static_au": round(d_static, 2),
        "err_static_pct": round(100 * (d_static - d_true) / d_true, 1),
        "within_20px_range_au": [round(float(ok.min()), 1), round(float(ok.max()), 1)] if ok.size else None,
    }


if __name__ == "__main__":
    rows = [
        run("neptune", "2025-06-24"),
        run("neptune", "2025-12-21"),
        run("uranus", "2025-08-25"),
        run("uranus", "2026-02-17"),
        run("saturn"),
    ]
    hdr = "| Body | Epoch pair | d true | d fit | err % | residual \" | static-only fit | static err % | 20px window AU |"
    print(hdr)
    print("|" + "---|" * 9)
    for r in rows:
        print(f"| {r['body']} | {r['epoch_pair']} | {r['d_true_au']} | {r['d_fit_au']} | {r['err_pct']} | "
              f"{r['residual_arcsec']} | {r['d_fit_static_au']} | {r['err_static_pct']} | {r['within_20px_range_au']} |")
    out = Path(__file__).resolve().parents[1] / "docs" / "validation_geometry.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rows, indent=2))
    print("wrote", out)
