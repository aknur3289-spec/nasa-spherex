"""Train and evaluate the real/bogus classifier.

Model: scikit-learn HistGradientBoostingClassifier on the features in ml/features.py.
Evaluation: grouped K-fold (a group = one exposure or one image pair), so detections from the
same image never sit in both train and test. Reports ROC AUC, average precision, and the recall
kept when only the top-ranked candidates are shown (what a volunteer queue cares about).

Run on real data:   python3 -m ml.train --data data/meta/ml/candidates.csv
Run on synthetic:   python3 -m ml.train --synthetic        (sanity check only; no science claim)
Outputs: <out>/model.joblib, <out>/metrics.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold

from ml.blind import ROOT
from ml.features import FEATURES

OUT = ROOT / "data" / "meta" / "ml"


def make_model(seed: int = 0) -> HistGradientBoostingClassifier:
    # small, regularised trees: real training sets are a few hundred to a few thousand rows
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=15,
                                          min_samples_leaf=10, l2_regularization=1.0,
                                          class_weight="balanced", random_state=seed)


def recall_at_purity(y: np.ndarray, p: np.ndarray, purity: float = 0.9) -> float:
    """Largest share of real objects kept while the shown list stays >= `purity` real."""
    order = np.argsort(-p)
    ys = y[order]
    tp = np.cumsum(ys)
    prec = tp / np.arange(1, len(ys) + 1)
    ok = np.nonzero(prec >= purity)[0]
    return float(tp[ok.max()] / max(ys.sum(), 1)) if len(ok) else 0.0


def evaluate(df: pd.DataFrame, n_splits: int = 5, seed: int = 0) -> tuple[dict, np.ndarray]:
    X, y = df[FEATURES].to_numpy(float), df["label"].to_numpy(int)
    w = df["weight"].to_numpy(float) if "weight" in df else np.ones(len(df))
    groups = df["group"].to_numpy()
    n_splits = max(2, min(n_splits, len(np.unique(groups))))
    oof = np.full(len(df), np.nan)
    for tr, te in GroupKFold(n_splits=n_splits).split(X, y, groups):
        if len(np.unique(y[tr])) < 2:
            continue
        m = make_model(seed).fit(X[tr], y[tr], sample_weight=w[tr])
        oof[te] = m.predict_proba(X[te])[:, 1]
    done = np.isfinite(oof)
    yy, pp = y[done], oof[done]
    metrics = {
        "n": int(len(df)), "n_real": int(y.sum()), "n_bogus": int((1 - y).sum()), "folds": n_splits,
        "roc_auc": float(roc_auc_score(yy, pp)) if len(np.unique(yy)) > 1 else None,
        "average_precision": float(average_precision_score(yy, pp)) if len(np.unique(yy)) > 1 else None,
        "recall_at_90pct_purity": recall_at_purity(yy, pp, 0.9),
        "baseline_z_roc_auc": float(roc_auc_score(yy, df["z"].to_numpy()[done])) if len(np.unique(yy)) > 1 else None,
    }
    if "kind" in df:  # how well each artefact type is pushed down (share scored < 0.5)
        k = df["kind"].to_numpy()[done]
        metrics["rejected_share_by_kind"] = {kk: float((pp[k == kk] < 0.5).mean()) for kk in np.unique(k) if (k == kk).any()}
    return metrics, oof


def fit_final(df: pd.DataFrame, seed: int = 0) -> tuple[HistGradientBoostingClassifier, dict]:
    X, y = df[FEATURES].to_numpy(float), df["label"].to_numpy(int)
    w = df["weight"].to_numpy(float) if "weight" in df else np.ones(len(df))
    model = make_model(seed).fit(X, y, sample_weight=w)
    imp = permutation_importance(model, X, y, n_repeats=5, random_state=seed, scoring="roc_auc")
    importance = dict(sorted(zip(FEATURES, map(float, imp.importances_mean)), key=lambda kv: -kv[1]))
    return model, importance


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=OUT / "candidates.csv")
    ap.add_argument("--synthetic", action="store_true", help="train on synthetic scenes instead")
    ap.add_argument("--scenes", type=int, default=300)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    if args.synthetic:
        from ml.synthetic import build
        df, _ = build(args.scenes, seed=0)
        out = args.out or OUT / "synthetic"
    else:
        df = pd.read_csv(args.data)
        out = args.out or args.data.parent
    out.mkdir(parents=True, exist_ok=True)
    metrics, oof = evaluate(df)
    model, importance = fit_final(df)
    metrics.update({"feature_importance": importance, "features": FEATURES,
                    "synthetic": bool(args.synthetic), "data": "synthetic" if args.synthetic else str(args.data)})
    joblib.dump({"model": model, "features": FEATURES, "synthetic": bool(args.synthetic)}, out / "model.joblib")
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    pd.DataFrame({"oof_score": oof}).to_csv(out / "oof_scores.csv", index=False)
    print(json.dumps({k: v for k, v in metrics.items() if k != "features"}, indent=2))


if __name__ == "__main__":
    main()
