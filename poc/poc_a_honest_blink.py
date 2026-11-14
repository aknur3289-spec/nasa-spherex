"""Offline PoC A: compare wavelength-matched SPHEREx epochs with a naive baseline."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import AsinhNorm
import numpy as np
import pandas as pd
import yaml
from astropy.time import Time
from reproject import reproject_interp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from spx.frame import read_frame  # noqa: E402
from spx.pairs import assign_survey_pass, match_pairs, naive_pairs, survey_pass_mids  # noqa: E402


with (ROOT / "pipeline" / "fields.yaml").open() as source:
    COORDS_DEG = {field["id"]: (float(field["ra"]), float(field["dec"]))
                  for field in yaml.safe_load(source)["fields"] if field.get("enabled")}


def _pair_dict(row: pd.Series | None) -> dict | None:
    return None if row is None else {key: (value.item() if isinstance(value, np.generic) else value)
                                    for key, value in row.items()}


def _project_pair(pair: pd.Series, frames: pd.DataFrame, ra_deg: float,
                  dec_deg: float) -> tuple[float, tuple[np.ndarray, np.ndarray, np.ndarray], dict]:
    by_id = frames.set_index("frame_id")
    a_row, b_row = by_id.loc[pair["a"]], by_id.loc[pair["b"]]
    a = read_frame(ROOT / a_row["local_path"], ra_deg, dec_deg)
    b = read_frame(ROOT / b_row["local_path"], ra_deg, dec_deg)
    shape = a.image.shape
    b_image, footprint = reproject_interp((b.image, b.wcs), a.wcs, shape_out=shape)
    b_bad, _ = reproject_interp((b.bad.astype(float), b.wcs), a.wcs, shape_out=shape)
    b_variance, _ = reproject_interp((b.variance, b.wcs), a.wcs, shape_out=shape)
    valid = (~a.bad & (b_bad <= 0.1) & (footprint > 0)
             & np.isfinite(a.image) & np.isfinite(b_image)
             & np.isfinite(a.variance) & np.isfinite(b_variance)
             & (a.variance > 0) & (b_variance > 0))
    if valid.sum() < 100:
        raise ValueError("fewer than 100 overlapping unmasked pixels")
    bright = valid & (a.image >= np.percentile(a.image[valid], 98)) & (b_image > 0)
    ratios = a.image[bright] / b_image[bright]
    ratios = ratios[np.isfinite(ratios) & (ratios > 0)]
    if not ratios.size:
        raise ValueError("no positive bright-pixel ratios for scale")
    scale = float(np.median(ratios))
    difference = a.image - scale * b_image
    residual = difference[valid]
    robust_std = float(1.4826 * np.median(np.abs(residual - np.median(residual))))
    noise = float(np.median(np.sqrt(a.variance[valid] + scale**2 * b_variance[valid])))
    if not np.isfinite(noise) or noise <= 0:
        raise ValueError("invalid combined variance noise")
    arrays = tuple(np.where(valid, array, np.nan) for array in (a.image, scale * b_image, difference))
    return robust_std / noise, arrays, {"scale_b": scale, "noise_mjysr": noise,
                                        "overlap_pixels": int(valid.sum())}


def _draw(field_id: str, frames: pd.DataFrame | None, pairs: dict,
          arrays: dict, out: Path, message: str) -> None:
    fig, axes = plt.subplots(2, 4, figsize=(15, 7), constrained_layout=True)
    for row_index, kind in enumerate(("honest", "naive_gap")):
        pair = pairs.get(kind)
        if pair is None or kind not in arrays:
            for ax in axes[row_index, :3]:
                ax.axis("off")
            axes[row_index, 1].text(0.5, 0.5, f"{kind}: unavailable\n{message}",
                                    ha="center", va="center", transform=axes[row_index, 1].transAxes)
            continue
        images = arrays[kind]
        values = np.concatenate([img[np.isfinite(img)] for img in images])
        limit = max(float(np.percentile(np.abs(values), 99)), 1e-9)
        norm = AsinhNorm(linear_width=limit / 20, vmin=-limit, vmax=limit)
        for col, (ax, image, label) in enumerate(zip(axes[row_index, :3], images,
                                                    ("A", "scaled B on A WCS", "A − scaled B"))):
            ax.imshow(image, origin="lower", cmap="coolwarm", norm=norm)
            ax.set_title(label)
            ax.set_xticks([]); ax.set_yticks([])
        times = frames.set_index("frame_id")["obs_time_utc"]
        axes[row_index, 1].set_xlabel(
            f"{kind}: {pair['wl_a_um']:.4f} / {pair['wl_b_um']:.4f} µm; "
            f"Δλ={100 * pair['dlam_frac']:.2f}%; Δt={pair['dt_days']:.1f} d\n"
            f"{times[pair['a']][:10]} / {times[pair['b']][:10]}")
    for ax in axes[:, 3]:
        ax.set_ylabel("Wavelength (µm)")
        ax.set_xlabel("MJD")
        if frames is not None:
            for detector, group in frames.groupby("detector"):
                ax.scatter(group["mjd"], group["wavelength_um"], s=12, label=f"D{detector}")
            by_id = frames.set_index("frame_id")
            for _, pair in pairs.get("all_honest", pd.DataFrame()).iterrows():
                a, b = by_id.loc[pair["a"]], by_id.loc[pair["b"]]
                ax.plot([a["mjd"], b["mjd"]], [a["wavelength_um"], b["wavelength_um"]],
                        color="black", alpha=0.3, linewidth=0.6)
            ax.legend(fontsize=7)
    fig.suptitle(f"PoC A — {field_id} — {message}")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    plt.close(fig)


def run_field(field_id: str) -> dict:
    directory = ROOT / "data" / "meta" / field_id
    path = directory / "epochs.csv"
    summary = {"field_id": field_id, "status": "missing_epochs", "n_frames": 0,
               "n_passes": 0, "pass_mid_mjd": {}, "pass_mid_utc": {},
               "n_pairs_strict": 0, "n_pairs_loose": 0, "pairs_per_detector": {},
               "best_pair": None, "naive_gap_pair": None, "R_honest": None,
               "R_naive": None, "verdict": "unavailable", "residual_error": None}
    if not path.is_file():
        _draw(field_id, None, {}, {}, directory / "poc_a.png", "epochs.csv missing")
    else:
        frames = pd.read_csv(path)
        frames["survey_pass"] = assign_survey_pass(frames["mjd"].to_numpy())
        mids = survey_pass_mids(frames["mjd"].to_numpy(), frames["survey_pass"].to_numpy())
        strict = match_pairs(frames, max_dlam_frac=0.02)
        loose = match_pairs(frames, max_dlam_frac=0.05)
        naive = naive_pairs(frames)
        naive_gap = naive.loc[naive["kind"].eq("naive_gap")]
        best = strict.iloc[0] if not strict.empty else (loose.iloc[0] if not loose.empty else None)
        gap = naive_gap.iloc[0] if not naive_gap.empty else None
        summary.update(status="ok", n_frames=len(frames), n_passes=len(mids),
                       pass_mid_mjd={str(k): v for k, v in mids.items()},
                       pass_mid_utc={str(k): Time(v, format="mjd", scale="utc").isot + "Z"
                                     for k, v in mids.items()},
                       n_pairs_strict=len(strict), n_pairs_loose=len(loose),
                       pairs_per_detector={str(int(detector)): {
                           "strict": len(match_pairs(group, max_dlam_frac=0.02,
                                                     max_pairs=100000)),
                           "loose": len(match_pairs(group, max_dlam_frac=0.05,
                                                    max_pairs=100000))}
                           for detector, group in frames.groupby("detector")},
                       best_pair=_pair_dict(best), naive_gap_pair=_pair_dict(gap),
                       verdict="meets_pair_target" if len(strict) >= 3 else "insufficient_strict_pairs")
        arrays = {}
        ra_deg, dec_deg = COORDS_DEG[field_id]
        for kind, pair in (("honest", best), ("naive_gap", gap)):
            if pair is None:
                continue
            try:
                ratio, arrays[kind], details = _project_pair(pair, frames, ra_deg, dec_deg)
                summary["R_honest" if kind == "honest" else "R_naive"] = ratio
                summary[kind + "_residual"] = details
            except (OSError, ValueError, KeyError) as exc:
                summary["residual_error"] = f"{kind}: {exc}"
        strict.to_csv(directory / "pairs.csv", index=False)
        _draw(field_id, frames, {"honest": best, "naive_gap": gap, "all_honest": strict},
              arrays, directory / "poc_a.png", summary["verdict"])
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "poc_a_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    return summary


def write_report(results: list[dict], verdict: str) -> None:
    doc = ROOT / "docs" / "EXPERIMENTS.md"
    lines = ["# Experiments", "", "## PoC A — Honest Blink", "",
             f"Run: {datetime.now(timezone.utc).isoformat(timespec='seconds')}. "
             "Offline input paths: `data/meta/{m101,nep,ecl}/epochs.csv` and local FITS cutouts; "
             "missing inputs are shown in the table.", "",
             "Passes use gaps >45 days. Strict pairs require Δλ ≤2% and Δt ≥150 days; "
             "loose pairs allow Δλ ≤5%. Pair counts are selected outputs (cap 12 per field). "
             "R uses MAD of the reprojected, masked difference divided by median combined variance noise; "
             "B scale is the median positive A/B ratio in the brightest 2% of valid A pixels.", "",
             "| Field | Frames | Passes | Strict | Loose | R honest | R naive | Status |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for result in results:
        fmt = lambda value: f"{value:.3f}" if value is not None else "—"
        lines.append(f"| {result['field_id']} | {result['n_frames']} | {result['n_passes']} | "
                     f"{result['n_pairs_strict']} | {result['n_pairs_loose']} | "
                     f"{fmt(result['R_honest'])} | {fmt(result['R_naive'])} | {result['status']} |")
    lines += ["", f"H1: **{verdict}**. Success requires at least 3 strict pairs in at least 2 of 3 fields.", "",
             "Per-detector selected pair counts (strict/loose, no 12-pair field cap):"]
    for result in results:
        counts = ", ".join(f"D{d} {v['strict']}/{v['loose']}"
                           for d, v in result["pairs_per_detector"].items()) or "none"
        lines.append(f"- {result['field_id']}: {counts}.")
    lines += ["", "Limitations: NEP has one pass under the 45-day gap rule, so no cross-pass pairs. "
              "ECL has no local epochs.csv; no network or deep-collection search was attempted. "
              "The M101 residual pairs use different detectors and dates. "
              "Residuals are diagnostic for the selected pairs, not a controlled significance test.", ""]
    doc.write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fields", nargs="+", choices=COORDS_DEG, default=list(COORDS_DEG))
    args = parser.parse_args()
    results = [run_field(field_id) for field_id in args.fields]
    verdict = "PASS" if sum(r["n_pairs_strict"] >= 3 for r in results) >= 2 else "FAIL"
    write_report(results, verdict)
    for result in results:
        print(f"{result['field_id']}: {result['n_pairs_strict']} strict, "
              f"{result['n_pairs_loose']} loose; R={result['R_honest']}/{result['R_naive']}")
    print(f"H1 {verdict}: {sum(r['n_pairs_strict'] >= 3 for r in results)}/{len(results)} fields")


if __name__ == "__main__":
    main()
