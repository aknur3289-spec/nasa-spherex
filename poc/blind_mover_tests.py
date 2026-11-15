"""Two checks on the blind detector: (1) mask ablation on Neptune, (2) injection-recovery depth.

(1) Re-run detection with the standard Honest Blink mask (OUTLIER/TRANSIENT masked).
(2) Inject a Gaussian point source (SPHEREx PSF) into science frames of the no-planet control
    pairs at known positions and fluxes, run the same difference + detection, count recoveries.
Run: python3 poc/blind_mover_tests.py   (offline)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from astropy.coordinates import SkyCoord
import astropy.units as u

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blind_mover as bm  # noqa: E402
from spx.frame import BAD_BITS  # noqa: E402

ROOT, OUT, PIX = bm.ROOT, bm.OUT, bm.PIX


def ablation() -> dict:
    eph = pd.read_csv(ROOT / "data/meta/neptune/epochs.csv").set_index("obs_id")
    res = {}
    for name, bits in (("mover_mask", bm.MOVER_BAD_BITS), ("standard_mask", BAD_BITS)):
        bm.MASK_BITS = bits
        found = total = 0
        for s, ref_path, _, _ in bm.neptune_pairs():
            sci = bm.load(ROOT / s.local_path)
            d = bm.difference(sci, bm.load(ref_path))
            total += 1
            if d is None:
                continue
            c = bm.detect(d, sci["wcs"])
            if c:
                sep = SkyCoord([x["ra"] for x in c] * u.deg, [x["dec"] for x in c] * u.deg).separation(
                    SkyCoord(eph.loc[s.obs_id, "eph_ra"] * u.deg, eph.loc[s.obs_id, "eph_dec"] * u.deg)).arcsec
                found += int((sep < 2 * PIX).any())
        res[name] = {"neptune_found": found, "differences": total}
    bm.MASK_BITS = bm.MOVER_BAD_BITS
    return res


def gaussian(shape, x0, y0, peak, fwhm_px):
    yy, xx = np.indices(shape)
    s = fwhm_px / 2.3548
    return peak * np.exp(-((xx - x0) ** 2 + (yy - y0) ** 2) / (2 * s * s))


def injection(levels=(3, 5, 7, 10, 15, 25, 50), per_frame=6, seed=7) -> list[dict]:
    """Peak amplitude in units of the frame's local noise (MAD of the science image)."""
    rng = np.random.default_rng(seed)
    rows = []
    for field in ("m101", "nep", "ecl"):
        ep = pd.read_csv(ROOT / f"data/meta/{field}/epochs.csv").set_index("frame_id")
        pr = pd.read_csv(ROOT / f"data/meta/{field}/pairs.csv")
        for _, p in pr[pr.trust == "high"].head(8).iterrows():
            a, b = ep.loc[p.a], ep.loc[p.b]
            sp, rp = ROOT / a.local_path, ROOT / b.local_path
            if not (sp.is_file() and rp.is_file()):
                continue
            sci0, ref = bm.load(sp), bm.load(rp)
            fwhm = float(a.psf_fwhm_arcsec) / PIX if np.isfinite(a.psf_fwhm_arcsec) else 1.2
            base = bm.difference(sci0, ref)
            if base is None:
                continue
            good = np.argwhere(base["ok"])
            noise = 1.4826 * np.median(np.abs(base["diff"][base["ok"]]))
            before = {(round(c["x"]), round(c["y"])) for c in bm.detect(base, sci0["wcs"])}
            for lv in levels:
                sci = dict(sci0)
                img = sci0["img"].copy()
                pos = []
                for _ in range(per_frame):
                    y, x = good[rng.integers(len(good))]
                    if min(x, y) < 8 or x > img.shape[1] - 9 or y > img.shape[0] - 9:
                        continue
                    img += gaussian(img.shape, x + rng.uniform(-.5, .5), y + rng.uniform(-.5, .5), lv * noise, fwhm)
                    pos.append((x, y))
                sci["img"] = img
                d = bm.difference(sci, ref)
                cands = bm.detect(d, sci["wcs"]) if d is not None else []
                for x, y in pos:
                    hit = any(np.hypot(c["x"] - x, c["y"] - y) < 2 and (round(c["x"]), round(c["y"])) not in before for c in cands)
                    rows.append({"field": field, "pair": f"{p.a}-{p.b}", "level_sigma": lv, "found": hit,
                                 "fwhm_px": fwhm, "noise_mjysr": float(noise)})
    return rows


if __name__ == "__main__":
    out = {"ablation": ablation()}
    inj = pd.DataFrame(injection())
    inj.to_csv(OUT / "injection.csv", index=False)
    out["injection_recovery"] = inj.groupby("level_sigma").found.agg(["mean", "count"]).reset_index().to_dict("records")
    out["injection_noise_mjysr_median"] = float(inj.noise_mjysr.median())
    (OUT / "tests.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
