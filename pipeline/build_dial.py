"""Run synthetic or SPHEREx distance-dial focus curves and write a contract field."""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from astropy.time import Time
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spx.focus import dial_grid, focus_curve, summarize  # noqa: E402
from spx.horizons import ephem  # noqa: E402
from spx.stamps import SpherexProvider, SyntheticProvider  # noqa: E402

PIXEL_SCALE = 6.15
STAMP_SIZE = 64
STRETCH_LO, STRETCH_HI = -2.0, 80.0


def _mjd(time: Time) -> float:
    return float(time.utc.mjd)


def _save_png(stamp: np.ndarray, path: Path) -> None:
    data = np.nan_to_num(np.asarray(stamp, dtype=float), nan=0.0)
    lo, hi, soft = STRETCH_LO, STRETCH_HI, 8.0
    stretched = np.arcsinh(np.clip(data, lo, hi) / soft)
    pixels = np.clip((stretched - np.arcsinh(lo / soft)) * 255 /
                     (np.arcsinh(hi / soft) - np.arcsinh(lo / soft)), 0, 255).astype(np.uint8)
    Image.fromarray(pixels).save(path, format="PNG", optimize=True)


def _json_native(value):
    if isinstance(value, dict):
        return {key: _json_native(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_native(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", default="neptune-synthetic", help="lowercase field ID (default: neptune-synthetic)")
    parser.add_argument("--body", required=True, help="Horizons body name or ID")
    parser.add_argument("--t0", required=True, help="UTC start time (ISO date/time)")
    parser.add_argument("--dt-days", type=float, default=182.6)
    parser.add_argument("--dmin", type=float, default=15.0)
    parser.add_argument("--dmax", type=float, default=1000.0)
    parser.add_argument("--step-px", type=float, default=15.0)
    parser.add_argument("--provider", choices=("synthetic", "spherex"), default="synthetic")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "out")
    return parser


def build(args: argparse.Namespace) -> Path:
    if not args.id or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for ch in args.id):
        raise ValueError("--id must use lowercase ASCII letters, digits, hyphens, or underscores")
    t0 = Time(args.t0, scale="utc")
    if not math.isfinite(args.dt_days) or args.dt_days <= 0:
        raise ValueError("--dt-days must be positive")
    t1 = t0 + args.dt_days
    eph = ephem(args.body, [t0, t1])
    e0, e1 = eph
    ra0, dec0, truth = e0["ra_deg"], e0["dec_deg"], e0["r_au"]
    provider = (SyntheticProvider(e1["ra_deg"], e1["dec_deg"], pixel_scale_arcsec=PIXEL_SCALE,
                                  stamp_size=STAMP_SIZE)
                if args.provider == "synthetic" else SpherexProvider())
    distances = dial_grid(args.dmin, args.dmax, step_px=args.step_px)
    circular = focus_curve(ra0, dec0, t0, t1, distances, provider.get_diff_stamp)
    static = focus_curve(ra0, dec0, t0, t1, distances, provider.get_diff_stamp, orbit="static")
    control = focus_curve(ra0, dec0 + 1.0, t0, t1, distances, provider.get_diff_stamp)
    summaries = _json_native({
        "circular": summarize(circular, truth),
        "static_baseline": summarize(static, truth),
        "empty_sky_control": summarize(control, truth),
    })

    out_dir = args.out / args.id
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    if args.provider == "synthetic":
        provider.body_ra_deg, provider.body_dec_deg = ra0, dec0
        ref_stamp = provider.get_diff_stamp(ra0, dec0, t0)
        provider.body_ra_deg, provider.body_dec_deg = e1["ra_deg"], e1["dec_deg"]
    else:
        ref_stamp = provider.get_diff_stamp(ra0, dec0, t0)
    ref_id = "ref"
    _save_png(ref_stamp, out_dir / "ref.png")
    frames.append({"id": ref_id, "png": "ref.png", "obs_time_utc": t0.utc.isot + "Z",
                   "mjd": _mjd(t0), "survey_pass": 0, "detector": 0, "wavelength_um": 1.0,
                   "center": {"ra_deg": ra0, "dec_deg": dec0}, "bad_pixel_fraction": 0.0,
                   "stretch": {"kind": "asinh", "lo": STRETCH_LO, "hi": STRETCH_HI, "unit": "synthetic counts"},
                   "source_url": f"https://example.invalid/{args.id}/{ref_id}", "obs_id": ref_id,
                   "processing_version": "synthetic" if args.provider == "synthetic" else "spherex-stub"})
    for i, step in enumerate(circular, 1):
        frame_id = f"d{i:03d}"
        pred = step["pred"]
        stamp = provider.get_diff_stamp(pred["ra_deg"], pred["dec_deg"], t1)
        _save_png(stamp, out_dir / f"{frame_id}.png")
        step["frame"] = frame_id
        frames.append({"id": frame_id, "png": f"{frame_id}.png", "obs_time_utc": t1.utc.isot + "Z",
                       "mjd": _mjd(t1), "survey_pass": 1, "detector": 0, "wavelength_um": 1.0,
                       "center": pred, "bad_pixel_fraction": 0.0,
                       "stretch": {"kind": "asinh", "lo": STRETCH_LO, "hi": STRETCH_HI, "unit": "synthetic counts"},
                       "source_url": f"https://example.invalid/{args.id}/{frame_id}", "obs_id": frame_id,
                       "processing_version": "synthetic" if args.provider == "synthetic" else "spherex-stub"})

    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=Path(__file__).resolve().parents[1], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "n/a"
    field = {"schema_version": "1.0", "field_id": args.id, "kind": "dial",
             "title": f"{args.body.title()} distance dial ({args.provider})",
             "description": "Runtime-generated focus curve from star-subtracted difference stamps.",
             "center": {"ra_deg": ra0, "dec_deg": dec0}, "size_arcmin": STAMP_SIZE * PIXEL_SCALE / 60,
             "pixel_scale_arcsec": PIXEL_SCALE, "frames": frames, "pairs": [],
             "dial": {"reference_frame": ref_id, "model": "parallax + circular prograde ecliptic orbit",
                      "search_radius_px": 20, "steps": circular,
                      "peak_distance_au": summaries["circular"]["peak_distance_au"],
                      "truth": {"distance_au": truth, "source": e0.get("source", "unknown ephemeris")},
                      "negative_control_field": f"{args.id}-blank"},
             "provenance": {"mission": "SPHEREx", "archive": "synthetic provider" if args.provider == "synthetic" else "SPHEREx",
                            "collections": ["synthetic"] if args.provider == "synthetic" else ["SPHEREx"],
                            "doi": "n/a", "downloaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                            "pipeline_commit": commit, "cached": True, "synthetic": args.provider == "synthetic"}}
    (out_dir / "field.json").write_text(json.dumps(field, indent=2, allow_nan=False) + "\n")
    summary = {"runs": summaries, "truth_distance_au": truth, "ephemeris_source": e0.get("source", "unknown")}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    return out_dir


def main() -> None:
    build(_parser().parse_args())


if __name__ == "__main__":
    main()
