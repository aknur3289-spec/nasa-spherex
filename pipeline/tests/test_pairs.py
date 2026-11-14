"""Synthetic-only checks for survey-pass and pair-selection logic."""

from collections import Counter

import numpy as np
import pandas as pd
import pytest

from spx.pairs import (
    PAIR_COLUMNS, assign_survey_pass, dlam_frac, match_pairs, naive_pairs,
    survey_pass_mids, trust_of,
)


def frames() -> pd.DataFrame:
    rows = [
        ("f1", 100, 2, 1.200, 0.02, False, "ok"),
        ("f2", 101, 2, 1.500, 0.03, False, "ok"),
        ("f3", 102, 3, 2.000, 0.01, False, "ok"),
        ("f4", 300, 2, 1.205, 0.02, False, "ok"),
        ("f5", 301, 2, 1.800, 0.05, False, "ok"),
        ("f6", 302, 3, 2.010, 0.02, False, "ok"),
        ("f7", 500, 2, 1.210, 0.01, False, "ok"),
        ("f8", 501, 2, 1.700, 0.06, False, "ok"),
        ("f9", 502, 3, 2.020, 0.03, False, "ok"),
    ]
    return pd.DataFrame(rows, columns=[
        "frame_id", "mjd", "detector", "wavelength_um",
        "bad_pixel_fraction", "target_bad", "status",
    ])


def test_passes_follow_gaps_and_keep_input_order() -> None:
    times = np.array([400.0, 100.0, 170.0, 169.0, 500.0])
    passes = assign_survey_pass(times)
    assert passes.tolist() == [3, 1, 2, 2, 4]
    assert survey_pass_mids(times, passes) == {1: 100.0, 2: 169.5, 3: 400.0, 4: 500.0}
    assert assign_survey_pass(np.array([100.0, 145.0, 190.1])).tolist() == [1, 1, 2]


@pytest.mark.parametrize("gap,expected", [
    (0.02, "high"), (0.0201, "medium"),
    (0.05, "medium"), (0.0501, "low"),
])
def test_trust_boundaries(gap: float, expected: str) -> None:
    assert trust_of(gap) == expected
    assert dlam_frac(1.0, 1.02) == pytest.approx(0.02 / 1.01)


def test_honest_pairs_respect_filters_and_frame_use_limit() -> None:
    source = frames()
    source["target_bad"] = source["target_bad"].astype(object)
    source.loc[len(source)] = ["bad_target", 700, 2, 1.200, 0.01, True, "ok"]
    source.loc[len(source)] = ["bad_status", 701, 2, 1.200, 0.01, None, "error"]
    selected = match_pairs(source, max_dlam_frac=0.02, max_pairs=12)
    assert list(selected.columns) == PAIR_COLUMNS
    assert not selected.empty
    assert (selected["pass_a"] != selected["pass_b"]).all()
    assert (selected["dt_days"] >= 150).all()
    assert (selected["dlam_frac"] <= 0.02).all()
    assert (selected["trust"] == "high").all()
    assert (selected["kind"] == "honest").all()
    uses = Counter(selected["a"]) + Counter(selected["b"])
    assert max(uses.values()) <= 2
    assert not {"bad_target", "bad_status"} & set(uses)
    detector_by_id = source.set_index("frame_id")["detector"].to_dict()
    assert all(detector_by_id[row.a] == detector_by_id[row.b] == row.detector
               for row in selected.itertuples())


def test_pass_combination_diversity_before_repeats() -> None:
    selected = match_pairs(frames(), max_pairs=3)
    combos = {tuple(sorted((row.pass_a, row.pass_b))) for row in selected.itertuples()}
    assert len(selected) == len(combos) == 3


def test_honest_sort_prefers_cleaner_then_longer_gap() -> None:
    source = pd.DataFrame([
        ("a1", 100, 2, 1.0, 0.10, False, "ok"),
        ("a2", 100, 2, 1.2, 0.01, False, "ok"),
        ("b1", 300, 2, 1.0, 0.20, False, "ok"),
        ("b2", 300, 2, 1.2, 0.01, False, "ok"),
        ("b3", 310, 2, 1.2, 0.01, False, "ok"),
    ], columns=frames().columns)
    selected = match_pairs(source, max_pairs=1)
    assert (selected.iloc[0]["a"], selected.iloc[0]["b"]) == ("a2", "b3")


def test_strict_and_loose_wavelength_thresholds() -> None:
    source = pd.DataFrame([
        ("a", 100, 2, 1.0, 0.1, False, "ok"),
        ("b", 300, 2, 1.0408, 0.1, False, "ok"),
    ], columns=frames().columns)
    assert match_pairs(source, max_dlam_frac=0.02).empty
    selected = match_pairs(source, max_dlam_frac=0.05)
    assert len(selected) == 1
    assert selected.iloc[0]["trust"] == "medium"
    assert match_pairs(source, min_dt_days=201).empty


def test_naive_baselines_have_larger_wavelength_gap() -> None:
    source = frames()
    honest = match_pairs(source, max_dlam_frac=0.02)
    naive = naive_pairs(source, n=3)
    assert set(naive["kind"]) == {"naive_time", "naive_gap"}
    assert len(naive) == 6
    assert naive["dlam_frac"].max() > honest["dlam_frac"].max()
    gap = naive[naive["kind"] == "naive_gap"]
    assert (gap["dt_days"] >= 150).all()
    assert (gap["pass_a"] != gap["pass_b"]).all()
    assert (gap["trust"] == "low").all()
    time = naive[naive["kind"] == "naive_time"]
    ordered = source.sort_values("mjd")
    by_detector = {detector: group["frame_id"].tolist()
                   for detector, group in ordered.groupby("detector")}
    assert all(by_detector[row.detector].index(row.b)
               == by_detector[row.detector].index(row.a) + 1
               for row in time.itertuples())


def test_empty_and_invalid_inputs() -> None:
    assert match_pairs(frames().iloc[0:0]).empty
    assert naive_pairs(frames(), n=0).empty
    with pytest.raises(ValueError, match="finite"):
        assign_survey_pass(np.array([1.0, np.nan]))
    with pytest.raises(ValueError, match="positive"):
        dlam_frac(0, 1)
    with pytest.raises(ValueError, match="nonnegative"):
        trust_of(-0.1)
