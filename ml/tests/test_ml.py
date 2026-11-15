"""Offline checks for the real/bogus classifier (synthetic inputs only)."""
import json

import numpy as np
import pytest

from ml import export_review
from ml.features import FEATURES, extract, stamps
from ml.synthetic import build, label_candidates
from ml.train import evaluate, recall_at_purity


def _diff_dict(img):
    ok = np.ones(img.shape, bool)
    zeros = np.zeros(img.shape)
    return {"z": img.copy(), "ok": ok, "diff": img.copy(), "sci": img + 0.0, "ref": zeros}


def _gauss(shape, x0, y0, peak, fwhm):
    yy, xx = np.indices(shape)
    s = fwhm / 2.3548
    return peak * np.exp(-((xx - x0) ** 2 + (yy - y0) ** 2) / (2 * s * s))


def test_point_source_vs_hot_pixel_features():
    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, (41, 41))
    star = extract(_diff_dict(base + _gauss(base.shape, 20, 20, 30, 1.4)), 20, 20)
    hot = base.copy()
    hot[20, 20] += 30
    spike = extract(_diff_dict(hot), 20, 20)
    assert set(FEATURES) <= set(star)
    assert star["psf_corr"] > 0.8
    assert star["support_2sig"] >= 5 and spike["support_2sig"] <= 3
    assert spike["sharpness"] > star["sharpness"]


def test_stamps_have_fixed_size_and_mask():
    img = np.ones((30, 30))
    d = _diff_dict(img)
    d["ok"][0:5, :] = False
    st = stamps(d, 2, 2)
    assert st["sci"].shape == (21, 21)
    assert np.isnan(st["diff"][0, 0])


def test_label_matching():
    truth = [{"x": 10, "y": 10, "kind": "mover"}, {"x": 30, "y": 30, "kind": "ghost"}]
    cands = [{"x": 10.5, "y": 9.8}, {"x": 30, "y": 31}, {"x": 50, "y": 50}]
    assert label_candidates(cands, truth) == ["mover", "ghost", "noise"]


def test_recall_at_purity():
    y = np.array([1, 1, 0, 1, 0, 0])
    p = np.array([.9, .8, .7, .6, .2, .1])
    assert recall_at_purity(y, p, 1.0) == pytest.approx(2 / 3)
    assert recall_at_purity(y, p, 0.75) == pytest.approx(1.0)


@pytest.fixture(scope="module")
def synth():
    return build(80, seed=3, with_stamps=True)


def test_synthetic_has_both_classes_and_learns(synth):
    df, _ = synth
    assert df.label.sum() > 20 and (1 - df.label).sum() > 20
    metrics, oof = evaluate(df, n_splits=4)
    assert metrics["roc_auc"] > 0.9          # synthetic sanity check, not a science result
    assert np.isfinite(oof).mean() > 0.95


def test_export_queue(tmp_path, monkeypatch, synth):
    df, st = synth
    monkeypatch.setattr(export_review, "REVIEW", tmp_path)
    scores = np.linspace(0, 1, len(df))
    out = export_review.export(df, st, scores, "t", "T", "desc", synthetic=True,
                               model_info={"name": "x"}, gold_kinds={"mover": "real"}, max_items=10)
    q = json.loads((out / "queue.json").read_text())
    assert q["schema_version"] == "review-1.0" and q["synthetic"] is True
    assert len(q["candidates"]) == 10
    for c in q["candidates"]:
        assert 0 <= c["ml_score"] <= 1
        for rel in c["stamps"].values():
            assert (out / rel).is_file()
    idx = json.loads((tmp_path / "index.json").read_text())
    assert idx["sets"][0]["queue"] == "t/queue.json"
