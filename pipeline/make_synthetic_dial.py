"""End-to-end check of the focus-curve code on SYNTHETIC images (provenance.synthetic = true).

Neptune is rendered at its true ephemeris position on a random star field; the
dial must peak at ~30 AU, and the empty-sky control (1° away) must not peak.
Also writes a contract-shaped fixture `docs/fixture_dial_neptune_synthetic.json`
that the frontend (Participant 4) can use for DistanceDial/FocusCurve today.

Run: python pipeline/make_synthetic_dial.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from astropy.time import Time
import astropy.units as u

sys.path.insert(0, str(Path(__file__).parent))
from spx.geometry import predict_radec  # noqa: E402
from spx.horizons import _from_astropy  # noqa: E402
from spx.focus import focus_curve, summarize, dial_grid  # noqa: E402

PIX_ARCSEC = 6.15
STAMP = 64
rng = np.random.default_rng(42)


def make_sky(ra_c, dec_c, half_deg=6.0, density_per_deg2=150):
    n = int(density_per_deg2 * (2 * half_deg) ** 2)
    return {"ra": ra_c + rng.uniform(-half_deg, half_deg, n) / np.cos(np.radians(dec_c)),
            "dec": dec_c + rng.uniform(-half_deg, half_deg, n),
            "flux": 10 ** rng.uniform(1.0, 2.6, n)}


def render(sky, ra_c, dec_c, extra=()):
    img = rng.normal(0, 1.0, (STAMP, STAMP))
    yy, xx = np.mgrid[0:STAMP, 0:STAMP]
    c = (STAMP - 1) / 2
    ras = np.concatenate([sky["ra"], [e[0] for e in extra]])
    decs = np.concatenate([sky["dec"], [e[1] for e in extra]])
    fl = np.concatenate([sky["flux"], [e[2] for e in extra]])
    dra = ((ras - ra_c + 180) % 360 - 180) * np.cos(np.radians(dec_c))
    px = c - dra * 3600 / PIX_ARCSEC          # east to the left
    py = c + (decs - dec_c) * 3600 / PIX_ARCSEC
    m = (px > -5) & (px < STAMP + 5) & (py > -5) & (py < STAMP + 5)
    for x, y, f in zip(px[m], py[m], fl[m]):
        img += f / (2 * np.pi * 1.2 ** 2) * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * 1.2 ** 2))
    return img


def main():
    t0 = Time("2025-06-10")  # near Neptune's morning quadrature
    t1 = t0 + 182.6 * u.day
    e0, e1 = _from_astropy("neptune", Time([t0, t1]))
    truth = e0["r_au"]
    sky = make_sky(e1["ra_deg"], e1["dec_deg"])
    nep1 = (e1["ra_deg"], e1["dec_deg"], 5000.0)

    def stamp_with_neptune(ra, dec, t):
        # difference image: epoch t1 (Neptune present) minus a template epoch (Neptune elsewhere)
        return render(sky, ra, dec, extra=[nep1]) - render(sky, ra, dec)

    d_grid = dial_grid(15, 1000, step_px=15)
    print("grid steps:", len(d_grid))
    steps = focus_curve(e0["ra_deg"], e0["dec_deg"], t0, t1, d_grid, stamp_with_neptune)
    s = summarize(steps, truth)
    neg = focus_curve(e0["ra_deg"], e0["dec_deg"] + 1.0, t0, t1, d_grid, stamp_with_neptune)
    sn = summarize(neg)
    base = focus_curve(e0["ra_deg"], e0["dec_deg"], t0, t1, d_grid, stamp_with_neptune, orbit="static")
    sb = summarize(base, truth)
    print("Neptune (circular model):", s)
    print("Neptune (static, known-wrong):", sb)
    print("Empty-sky control:", sn)

    fixture = {
        "schema_version": "1.0", "field_id": "neptune-synthetic", "kind": "dial",
        "title": "Neptune, 30 AU (SYNTHETIC fixture)",
        "description": "Synthetic images; geometry from astropy ephemeris. For UI work only.",
        "center": {"ra_deg": round(e0["ra_deg"], 6), "dec_deg": round(e0["dec_deg"], 6)},
        "size_arcmin": round(STAMP * PIX_ARCSEC / 60, 2), "pixel_scale_arcsec": PIX_ARCSEC,
        "frames": [], "pairs": [],
        "dial": {"reference_frame": "ref", "model": "parallax + circular prograde ecliptic orbit",
                 "search_radius_px": 20, "steps": steps,
                 "peak_distance_au": s["peak_distance_au"],
                 "truth": {"distance_au": round(truth, 2), "source": "astropy builtin ephemeris"},
                 "negative_control_field": "neptune-synthetic-blank"},
        "provenance": {"mission": "SPHEREx", "archive": "none (synthetic)", "collections": [],
                       "doi": None, "downloaded_utc": None, "pipeline_commit": None,
                       "cached": True, "synthetic": True},
    }
    out = Path(__file__).resolve().parents[1] / "docs" / "fixture_dial_neptune_synthetic.json"
    out.write_text(json.dumps(fixture, indent=1))
    print("wrote", out)
    return s, sn


if __name__ == "__main__":
    main()
