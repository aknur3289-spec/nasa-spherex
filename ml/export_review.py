"""Write a ranked candidate queue + image stamps for the volunteer Review page.

Output (static files, read by web/src/survey/Review.tsx):
  web/public/data/review/index.json                 list of review sets
  web/public/data/review/<set_id>/queue.json        candidates, ML scores, stamp paths
  web/public/data/review/<set_id>/stamps/<id>_{sci,ref,diff}.png   21 x 21 px

Real set (after ml.dataset + ml.train on real data):
  python3 -m ml.export_review --data data/meta/ml/candidates.csv --model data/meta/ml/model.joblib --set-id blind-v1
Synthetic demo set (labelled DEMO DATA in the UI):
  python3 -m ml.export_review --synthetic-demo
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from PIL import Image

from ml.blind import ROOT
from ml.features import FEATURES

REVIEW = ROOT / "web" / "public" / "data" / "review"
SCHEMA = "review-1.0"
SHOW_FEATURES = ["z", "fwhm_px", "psf_corr", "sharpness", "new_flux_frac", "neg_pos_ratio"]


def _png(a: np.ndarray, lo: float, hi: float, out: Path, symmetric: bool = False) -> None:
    v = np.asarray(a, float)
    nan = ~np.isfinite(v)
    v = np.where(nan, 0.0, v)
    if symmetric:              # difference: mid-grey = 0, white = new flux, black = missing flux
        s = max(hi, 1e-9)
        g = 0.5 + 0.5 * np.arcsinh(v / (0.1 * s)) / np.arcsinh(10)
    else:
        g = np.arcsinh((v - lo) / max(0.05 * (hi - lo), 1e-9)) / np.arcsinh(20)
    g = (np.clip(g, 0, 1) * 255).astype(np.uint8)
    rgba = np.dstack([g, g, g, np.where(nan, 0, 255).astype(np.uint8)])
    Image.fromarray(rgba, "RGBA").save(out, optimize=True)


def write_stamps(st: dict[str, np.ndarray], out_dir: Path, cid: str) -> dict[str, str]:
    both = np.concatenate([st["sci"].ravel(), st["ref"].ravel()])
    both = both[np.isfinite(both)]
    lo, hi = (np.percentile(both, 5), np.percentile(both, 99.5)) if len(both) else (0.0, 1.0)
    d = st["diff"][np.isfinite(st["diff"])]
    dmax = float(np.percentile(np.abs(d), 99.5)) if len(d) else 1.0
    paths = {}
    for k in ("sci", "ref", "diff"):
        rel = f"stamps/{cid}_{k}.png"
        _png(st[k], lo, hi, out_dir / rel, symmetric=(k == "diff"))
        paths[k] = rel
    return paths


def priority(score: np.ndarray, rng: np.random.Generator, explore: float = 0.25) -> np.ndarray:
    """Queue order: mostly most-likely-real first, with uncertain cases mixed in (active learning)."""
    uncertain = 1 - 2 * np.abs(score - 0.5)
    pick = rng.random(len(score)) < explore
    return np.where(pick, uncertain, score)


def export(df: pd.DataFrame, st: dict, scores: np.ndarray, set_id: str, title: str, description: str,
           synthetic: bool, model_info: dict, gold_kinds: dict[str, str] | None = None,
           max_items: int = 120, seed: int = 0) -> Path:
    rng = np.random.default_rng(seed)
    out = REVIEW / set_id
    if out.exists():
        shutil.rmtree(out)
    (out / "stamps").mkdir(parents=True)
    df = df.assign(ml_score=scores, _prio=priority(scores, rng)).sort_values("_prio", ascending=False)
    df = df[df.index.isin(list(st))].head(max_items)
    items = []
    for n, (idx, r) in enumerate(df.iterrows()):
        cid = f"c{n:04d}"
        item = {"id": cid, "ra_deg": round(float(r.ra), 6), "dec_deg": round(float(r.dec), 6),
                "ml_score": round(float(r.ml_score), 4), "group": str(r.group),
                "stamps": write_stamps(st[idx], out, cid),
                "features": {k: (None if not np.isfinite(r[k]) else round(float(r[k]), 3)) for k in SHOW_FEATURES}}
        if "mjd" in r and pd.notna(r.get("mjd")):
            item["mjd"] = float(r.mjd)
        if gold_kinds is not None and str(r.kind) in gold_kinds:   # known answer, for the tutorial and QA
            item["gold"] = {"answer": gold_kinds[str(r.kind)], "kind": str(r.kind)}
        items.append(item)
    queue = {"schema_version": SCHEMA, "set_id": set_id, "title": title, "description": description,
             "synthetic": synthetic, "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "stamp_px": int(next(iter(st.values()))["sci"].shape[0]), "model": model_info, "candidates": items}
    (out / "queue.json").write_text(json.dumps(queue, indent=1))
    _update_index(set_id, title, synthetic, len(items))
    return out


def _update_index(set_id: str, title: str, synthetic: bool, n: int) -> None:
    path = REVIEW / "index.json"
    sets = json.loads(path.read_text())["sets"] if path.exists() else []
    sets = [s for s in sets if s["set_id"] != set_id] + [
        {"set_id": set_id, "title": title, "synthetic": synthetic, "n": n, "queue": f"{set_id}/queue.json"}]
    sets.sort(key=lambda s: (s["synthetic"], s["set_id"]))     # real sets first
    path.write_text(json.dumps({"schema_version": SCHEMA, "sets": sets}, indent=1))


def synthetic_demo() -> Path:
    from ml.synthetic import build
    from ml.train import evaluate, fit_final
    train_df, _ = build(300, seed=0)
    metrics, _ = evaluate(train_df)
    model, _ = fit_final(train_df)
    df, st = build(40, seed=99, with_stamps=True)              # unseen scenes for the queue
    scores = model.predict_proba(df[FEATURES].to_numpy(float))[:, 1]
    gold = {"mover": "real", "cosmic": "bogus", "dipole": "bogus", "ghost": "bogus", "streak": "bogus"}
    return export(df, st, scores, "demo-synthetic", "Practice set (synthetic)",
                  "Simulated SPHEREx-like difference images with known answers. Use it to learn what real "
                  "movers and artefacts look like. Nothing here is a real detection.",
                  synthetic=True, gold_kinds=gold,
                  model_info={"name": "HistGradientBoosting real/bogus", "trained_on": "synthetic",
                              "cv_roc_auc": round(metrics["roc_auc"], 3)})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--synthetic-demo", action="store_true")
    ap.add_argument("--data", type=Path)
    ap.add_argument("--model", type=Path)
    ap.add_argument("--set-id", default="blind-v1")
    ap.add_argument("--title", default="Blind search candidates")
    ap.add_argument("--max-items", type=int, default=200)
    args = ap.parse_args()
    if args.synthetic_demo:
        print("wrote", synthetic_demo())
        return
    df = pd.read_csv(args.data, index_col="cand_id")
    npz = np.load(args.data.parent / "stamps.npz")
    st = {}
    for key in npz.files:
        i, kind = key.rsplit("_", 1)
        st.setdefault(int(i), {})[kind] = npz[key]
    bundle = joblib.load(args.model)
    scores = bundle["model"].predict_proba(df[bundle["features"]].to_numpy(float))[:, 1]
    metrics_path = args.model.parent / "metrics.json"
    auc = json.loads(metrics_path.read_text()).get("roc_auc") if metrics_path.exists() else None
    out = export(df, st, scores, args.set_id, args.title,
                 "Candidates from the blind moving-object search on real SPHEREx data, ranked by the ML model. "
                 "Known answers (Neptune, injected test sources) are marked as practice items.",
                 synthetic=False, max_items=args.max_items,
                 gold_kinds={"mover": "real", "injected": "real", "neptune_other": "bogus"},
                 model_info={"name": "HistGradientBoosting real/bogus", "trained_on": str(args.data),
                             "cv_roc_auc": None if auc is None else round(auc, 3)})
    print("wrote", out)


if __name__ == "__main__":
    main()
