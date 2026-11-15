"""Labelled candidates from real SPHEREx data. Runs offline on the cached FITS in data/raw.

Labels (all from the existing blind-test inputs, see docs/BLIND_TEST.md):
  * Neptune frames: a candidate within 2 px of the JPL Horizons position is `mover` (real);
    every other candidate in those frames is `neptune_other` (bogus: ghosts, glare companions,
    static-star residuals). Horizons is used only to make labels, never as a model input.
  * Control fields (m101, nep, ecl, high-trust pairs): Gaussian point sources are injected into
    the science frame at 5-50x the pixel noise. Recovered injections are `injected` (real).
    Candidates that were already there before injection are `control` (presumed bogus; some
    may be real asteroids, so they get a lower sample weight).

Run:  python3 -m ml.dataset            -> data/meta/ml/candidates.csv, data/meta/ml/stamps.npz
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from astropy import units as u
from astropy.coordinates import SkyCoord

from ml.blind import ROOT, bm
from ml.features import extract, stamps

OUT = ROOT / "data" / "meta" / "ml"
MATCH_PX = 2.0
WEIGHT = {"mover": 1.0, "neptune_other": 1.0, "injected": 1.0, "control": 0.5}


def _gaussian(shape, x0, y0, peak, fwhm_px):
    yy, xx = np.indices(shape)
    s = fwhm_px / 2.3548
    return peak * np.exp(-((xx - x0) ** 2 + (yy - y0) ** 2) / (2 * s * s))


def _row(d, c, kind, group, source, extra=None):
    return {**extract(d, c["x"], c["y"]), "x": c["x"], "y": c["y"], "ra": c["ra"], "dec": c["dec"],
            "kind": kind, "label": int(kind in ("mover", "injected")), "weight": WEIGHT[kind],
            "group": group, "source": source, **(extra or {})}


def neptune_rows(rows: list, st: dict) -> None:
    eph = pd.read_csv(ROOT / "data/meta/neptune/epochs.csv").set_index("obs_id")
    for s, ref_path, ref_id, dlam in bm.neptune_pairs():
        sci = bm.load(ROOT / s.local_path)
        d = bm.difference(sci, bm.load(ref_path))
        if d is None:
            continue
        cands = bm.detect(d, sci["wcs"])
        if not cands:
            continue
        sep = SkyCoord([c["ra"] for c in cands] * u.deg, [c["dec"] for c in cands] * u.deg).separation(
            SkyCoord(eph.loc[s.obs_id, "eph_ra"] * u.deg, eph.loc[s.obs_id, "eph_dec"] * u.deg)).arcsec
        for c, r in zip(cands, sep):
            kind = "mover" if r < MATCH_PX * bm.PIX else "neptune_other"
            st[len(rows)] = stamps(d, c["x"], c["y"])
            rows.append(_row(d, c, kind, f"neptune:{s.obs_id}", "neptune",
                             {"obs_id": s.obs_id, "ref_obs_id": ref_id, "mjd": sci["mjd"], "dlam": dlam}))


def control_rows(rows: list, st: dict, per_frame: int = 6, seed: int = 11) -> None:
    rng = np.random.default_rng(seed)
    for field in ("m101", "nep", "ecl"):
        ep = pd.read_csv(ROOT / f"data/meta/{field}/epochs.csv").set_index("frame_id")
        pr = pd.read_csv(ROOT / f"data/meta/{field}/pairs.csv")
        for _, p in pr[pr.trust == "high"].iterrows():
            a, b = ep.loc[p.a], ep.loc[p.b]
            sp, rp = ROOT / a.local_path, ROOT / b.local_path
            if not (sp.is_file() and rp.is_file()):
                continue
            sci0, ref = bm.load(sp), bm.load(rp)
            base = bm.difference(sci0, ref)
            if base is None:
                continue
            group = f"{field}:{p.a}-{p.b}"
            before = bm.detect(base, sci0["wcs"])
            for c in before:
                st[len(rows)] = stamps(base, c["x"], c["y"])
                rows.append(_row(base, c, "control", group, field))
            # injections: one new science frame per pair with several sources of random depth
            fwhm = float(a.psf_fwhm_arcsec) / bm.PIX if np.isfinite(a.psf_fwhm_arcsec) else 1.2
            noise = 1.4826 * np.median(np.abs(base["diff"][base["ok"]]))
            good = np.argwhere(base["ok"])
            img, pos = sci0["img"].copy(), []
            for _ in range(per_frame):
                y, x = good[rng.integers(len(good))]
                if min(x, y) < 8 or x > img.shape[1] - 9 or y > img.shape[0] - 9:
                    continue
                x0, y0 = x + rng.uniform(-.5, .5), y + rng.uniform(-.5, .5)
                img += _gaussian(img.shape, x0, y0, noise * 10 ** rng.uniform(np.log10(5), np.log10(50)), fwhm)
                pos.append((x0, y0))
            d = bm.difference({**sci0, "img": img}, ref)
            if d is None:
                continue
            old = {(round(c["x"]), round(c["y"])) for c in before}
            for c in bm.detect(d, sci0["wcs"]):
                if (round(c["x"]), round(c["y"])) in old:
                    continue
                if any(np.hypot(c["x"] - x0, c["y"] - y0) < MATCH_PX for x0, y0 in pos):
                    st[len(rows)] = stamps(d, c["x"], c["y"])
                    rows.append(_row(d, c, "injected", group + ":inj", field))


def save(rows: list, st: dict, out: Path = OUT) -> pd.DataFrame:
    out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.index.name = "cand_id"
    df.to_csv(out / "candidates.csv")
    np.savez_compressed(out / "stamps.npz", **{f"{k}_{n}": v[n] for k, v in st.items() for n in ("sci", "ref", "diff")})
    (out / "dataset_summary.json").write_text(json.dumps(
        {"n": int(len(df)), "by_kind": df.kind.value_counts().to_dict(), "groups": int(df.group.nunique())}, indent=2))
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-neptune", action="store_true")
    ap.add_argument("--skip-controls", action="store_true")
    args = ap.parse_args()
    if not (ROOT / "data" / "raw").is_dir() or not any((ROOT / "data" / "raw").rglob("*.fits")):
        raise SystemExit("No cached SPHEREx FITS in data/raw/. Copy the team's data/ folder (raw + meta) from the "
                         "machine that ran poc/blind_mover.py, or fetch it with pipeline/fetch_neptune.py and "
                         "pipeline/fetch_field.py first.")
    rows, st = [], {}
    if not args.skip_neptune:
        neptune_rows(rows, st)
    if not args.skip_controls:
        control_rows(rows, st)
    df = save(rows, st)
    print(df.kind.value_counts().to_string())
    print(f"wrote {len(df)} candidates to {OUT}")


if __name__ == "__main__":
    main()
