"""Assign survey passes and select wavelength-matched blink pairs."""

from __future__ import annotations

import numpy as np
import pandas as pd


PAIR_COLUMNS = [
    "a", "b", "detector", "wl_a_um", "wl_b_um", "dlam_frac", "dt_days",
    "pass_a", "pass_b", "trust", "kind",
]
_REQUIRED_FRAME_COLUMNS = {
    "frame_id", "mjd", "detector", "wavelength_um", "bad_pixel_fraction",
    "target_bad", "status",
}


def assign_survey_pass(mjd: np.ndarray, gap_days: float = 45.0) -> np.ndarray:
    """Number chronological time clusters from 1, aligned to the input order."""
    times = np.asarray(mjd, dtype=float)
    if times.ndim != 1 or not np.isfinite(times).all():
        raise ValueError("mjd must be a one-dimensional array of finite values")
    if not np.isfinite(gap_days) or gap_days < 0:
        raise ValueError("gap_days must be finite and nonnegative")
    passes = np.empty(len(times), dtype=np.int64)
    if not len(times):
        return passes
    order = np.argsort(times, kind="stable")
    sorted_times = times[order]
    sorted_passes = 1 + np.cumsum(np.r_[False, np.diff(sorted_times) > gap_days])
    if sorted_passes[-1] == 1 and sorted_times[-1] - sorted_times[0] > 150:
        sorted_passes = 1 + np.floor((sorted_times - sorted_times[0]) / 182.6).astype(np.int64)
    passes[order] = sorted_passes
    return passes


def survey_pass_mids(mjd: np.ndarray, passes: np.ndarray) -> dict[int, float]:
    """Return the mid-MJD of each assigned pass for a passes.json summary."""
    times = np.asarray(mjd, dtype=float)
    numbers = np.asarray(passes)
    if times.ndim != 1 or numbers.ndim != 1 or times.shape != numbers.shape:
        raise ValueError("mjd and passes must be matching one-dimensional arrays")
    if not np.isfinite(times).all():
        raise ValueError("mjd must contain finite values")
    if not np.issubdtype(numbers.dtype, np.integer) or (numbers < 1).any():
        raise ValueError("passes must be positive integers")
    return {int(number): float((np.min(times[numbers == number])
                                + np.max(times[numbers == number])) / 2)
            for number in np.unique(numbers)}


def dlam_frac(wl_a_um: float, wl_b_um: float) -> float:
    """Return the symmetric fractional wavelength difference."""
    if not (np.isfinite(wl_a_um) and np.isfinite(wl_b_um)
            and wl_a_um > 0 and wl_b_um > 0):
        raise ValueError("wavelengths must be positive and finite in um")
    return float(abs(wl_a_um - wl_b_um) / ((wl_a_um + wl_b_um) / 2))


def trust_of(dlam: float) -> str:
    """Classify a fractional wavelength gap for the viewer contract."""
    if not np.isfinite(dlam) or dlam < 0:
        raise ValueError("dlam must be finite and nonnegative")
    if dlam <= 0.02:
        return "high"
    if dlam <= 0.05:
        return "medium"
    return "low"


def _target_is_bad(value: object) -> bool:
    if pd.isna(value):
        return True
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        if value.strip().lower() in {"false", "0"}:
            return False
        if value.strip().lower() in {"true", "1"}:
            return True
    raise ValueError(f"invalid target_bad value: {value!r}")


def _usable_frames(frames: pd.DataFrame) -> pd.DataFrame:
    missing = _REQUIRED_FRAME_COLUMNS - set(frames.columns)
    if missing:
        raise ValueError(f"missing frame columns: {', '.join(sorted(missing))}")
    work = frames.copy()
    for column in ("mjd", "detector", "wavelength_um", "bad_pixel_fraction"):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    work["target_bad"] = work["target_bad"].map(_target_is_bad)
    valid_times = np.isfinite(work["mjd"].to_numpy(dtype=float))
    supplied_passes = (pd.to_numeric(work["survey_pass"], errors="coerce")
                       if "survey_pass" in work else None)
    if supplied_passes is not None and supplied_passes.notna().all() and (
        (supplied_passes > 0) & (supplied_passes == np.floor(supplied_passes))
    ).all():
        work["survey_pass"] = supplied_passes.astype(int)
    else:
        assigned = np.zeros(len(work), dtype=np.int64)
        assigned[valid_times] = assign_survey_pass(work.loc[valid_times, "mjd"].to_numpy())
        work["survey_pass"] = assigned
    usable = work.loc[
        work["status"].eq("ok")
        & ~work["target_bad"]
        & valid_times
        & np.isfinite(work["detector"].to_numpy(dtype=float))
        & np.isfinite(work["wavelength_um"].to_numpy(dtype=float))
        & work["wavelength_um"].gt(0)
        & work["bad_pixel_fraction"].between(0, 1)
    ].copy()
    if usable["frame_id"].isna().any() or usable["frame_id"].duplicated().any():
        raise ValueError("usable frame_id values must be present and unique")
    return usable.sort_values(["mjd", "detector", "frame_id"], kind="stable")


def _pair(a: pd.Series, b: pd.Series, kind: str) -> dict:
    fraction = dlam_frac(float(a["wavelength_um"]), float(b["wavelength_um"]))
    return {
        "a": str(a["frame_id"]), "b": str(b["frame_id"]),
        "detector": int(a["detector"]),
        "wl_a_um": float(a["wavelength_um"]), "wl_b_um": float(b["wavelength_um"]),
        "dlam_frac": fraction, "dt_days": float(b["mjd"] - a["mjd"]),
        "pass_a": int(a["survey_pass"]), "pass_b": int(b["survey_pass"]),
        "trust": trust_of(fraction), "kind": kind,
        "_bad_sum": float(a["bad_pixel_fraction"] + b["bad_pixel_fraction"]),
    }


def _candidates(frames: pd.DataFrame, *, min_dt_days: float = 0) -> list[dict]:
    candidates = []
    for _, detector_frames in frames.groupby("detector", sort=True):
        rows = list(detector_frames.iterrows())
        for first in range(len(rows)):
            for second in range(first + 1, len(rows)):
                a, b = rows[first][1], rows[second][1]
                if b["mjd"] - a["mjd"] < min_dt_days:
                    continue
                candidates.append(_pair(a, b, "honest"))
    return candidates


def _output(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=PAIR_COLUMNS)


def _honest_sort_key(row: dict) -> tuple:
    return (row["dlam_frac"], row["_bad_sum"], -row["dt_days"], row["a"], row["b"])


def match_pairs(
    frames: pd.DataFrame, max_dlam_frac: float = 0.05,
    min_dt_days: float = 150.0, max_pairs: int = 12,
) -> pd.DataFrame:
    """Choose diverse same-detector pairs at least min_dt_days apart."""
    if not np.isfinite(max_dlam_frac) or max_dlam_frac < 0:
        raise ValueError("max_dlam_frac must be finite and nonnegative")
    if not np.isfinite(min_dt_days) or min_dt_days < 0:
        raise ValueError("min_dt_days must be finite and nonnegative")
    if not isinstance(max_pairs, int) or max_pairs < 0:
        raise ValueError("max_pairs must be a nonnegative integer")
    usable = _usable_frames(frames)
    candidates = [row for row in _candidates(usable, min_dt_days=min_dt_days)
                  if row["dlam_frac"] <= max_dlam_frac]
    candidates.sort(key=_honest_sort_key)
    selected = []
    frame_uses: dict[str, int] = {}
    covered_pass_pairs: set[tuple[int, int]] = set()
    used_pairs: set[tuple[str, str]] = set()
    for unique_passes_only in (True, False):
        for row in candidates:
            if len(selected) >= max_pairs:
                return _output(sorted(selected, key=_honest_sort_key))
            pass_pair = tuple(sorted((row["pass_a"], row["pass_b"])))
            pair_ids = (row["a"], row["b"])
            if pair_ids in used_pairs or (unique_passes_only and pass_pair in covered_pass_pairs):
                continue
            if frame_uses.get(row["a"], 0) >= 2 or frame_uses.get(row["b"], 0) >= 2:
                continue
            selected.append(row)
            used_pairs.add(pair_ids)
            covered_pass_pairs.add(pass_pair)
            for frame_id in pair_ids:
                frame_uses[frame_id] = frame_uses.get(frame_id, 0) + 1
    return _output(sorted(selected, key=_honest_sort_key))


def naive_pairs(frames: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """Return up to n consecutive-time and n long-gap baseline pairs."""
    if not isinstance(n, int) or n < 0:
        raise ValueError("n must be a nonnegative integer")
    usable = _usable_frames(frames)
    consecutive = []
    for _, detector_frames in usable.groupby("detector", sort=True):
        rows = [row for _, row in detector_frames.iterrows()]
        consecutive.extend(_pair(a, b, "naive_time") for a, b in zip(rows, rows[1:]))
    consecutive.sort(key=lambda row: (-row["dlam_frac"], -row["dt_days"], row["a"], row["b"]))
    long_gap = _candidates(usable, min_dt_days=150.0)
    for row in long_gap:
        row["kind"] = "naive_gap"
    long_gap.sort(key=lambda row: (-row["dlam_frac"], -row["dt_days"], row["a"], row["b"]))
    return _output(consecutive[:n] + long_gap[:n])
