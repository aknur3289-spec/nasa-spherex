"""Build one static Honest Blink field from cached SPHEREx frames."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.spx.frame import build_epochs, read_frame
from pipeline.spx.io import fetch_field
from pipeline.spx.manifest import update_index, write_field
from pipeline.spx.pairs import assign_survey_pass, match_pairs, naive_pairs

CONFIG_PATH = Path(__file__).with_name("fields.yaml")
DATA_ROOT = Path("web/public/data")


def _config(field_id: str, config_path: Path) -> dict:
    settings = yaml.safe_load(config_path.read_text())
    matches = [item for item in settings["fields"] if item["id"] == field_id]
    if len(matches) != 1:
        raise ValueError(f"field {field_id!r} is not uniquely configured")
    field = {**settings.get("defaults", {}), **matches[0]}
    if not field.get("enabled", False):
        raise ValueError(f"field {field_id!r} is disabled")
    return field


def _commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()


def _downloaded_utc(value: str) -> str:
    """Normalize a recorded, timezone-aware download timestamp to UTC."""
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("downloaded_utc must include a UTC offset")
    return stamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _pairs(honest: pd.DataFrame, naive: pd.DataFrame) -> list[dict]:
    ordered = []
    for trust in ("high", "medium", "low"):
        group = pd.concat((honest.loc[honest["trust"].eq(trust)],
                           naive.loc[naive["trust"].eq(trust)]))
        for row in group.to_dict("records"):
            ordered.append({"a": str(row["a"]), "b": str(row["b"]),
                            "dlambda_frac": float(row["dlam_frac"]),
                            "dt_days": float(row["dt_days"]), "trust": str(row["trust"])})
    return ordered


def build_field(
    field_id: str, *, offline: bool = False, max_frames: int | None = None,
    config_path: Path = CONFIG_PATH, data_root: Path = DATA_ROOT,
    synthetic: bool = False,
) -> dict:
    """Build field assets; synthetic is reserved for isolated offline fixtures."""
    from pipeline.spx import render

    field = _config(field_id, config_path)
    ra_deg, dec_deg = float(field["ra"]), float(field["dec"])
    size_arcmin = float(field["size_arcmin"])
    if not offline:
        fetch_field(field_id, ra_deg, dec_deg, size_arcmin / 60,
                    detectors=list(field["detectors"]), limit=max_frames or field.get("limit"))
    epochs_path = build_epochs(field_id, ra_deg, dec_deg)
    epochs = pd.read_csv(epochs_path, keep_default_na=False)
    if epochs.empty:
        raise ValueError(f"{field_id}: no cached epochs")
    valid = pd.to_numeric(epochs["mjd"], errors="coerce")
    valid = np.isfinite(valid.to_numpy(dtype=float))
    passes = np.zeros(len(epochs), dtype=int)
    passes[valid] = assign_survey_pass(epochs.loc[valid, "mjd"].to_numpy(dtype=float))
    epochs["survey_pass"] = passes
    epochs.to_csv(epochs_path, index=False)
    honest = match_pairs(epochs)
    naive = naive_pairs(epochs)
    pairs = _pairs(honest, naive)
    if not pairs:
        raise ValueError(f"{field_id}: no usable pairs")
    if honest.empty:
        print(f"WARNING {field_id}: zero honest pairs; publishing naive pairs only")
    ids = {pair[side] for pair in pairs for side in ("a", "b")}
    published = epochs.loc[epochs["frame_id"].isin(ids)].sort_values("frame_id")
    downloads = [str(value) for value in published["downloaded_utc"]]
    if any(not value or value == "nan" for value in downloads):
        raise ValueError(f"{field_id}: published frames lack downloaded_utc")
    frames = {}
    grid_wcs, shape = render.field_grid(ra_deg, dec_deg, size_arcmin)
    projected = {}
    for row in published.to_dict("records"):
        frame_id = str(row["frame_id"])
        frames[frame_id] = row
        frame = read_frame(Path(row["local_path"]), ra_deg, dec_deg)
        projected[frame_id] = render.to_grid_with_footprint(frame, grid_wcs, shape)
    stretches = {}
    for detector in sorted(published["detector"].unique()):
        detector_ids = [frame_id for frame_id, row in frames.items() if row["detector"] == detector]
        stretches[detector] = render.stretch_params([projected[frame_id][0] for frame_id in detector_ids])
    outdir = data_root / field_id
    outdir.mkdir(parents=True, exist_ok=True)
    center = {"ra_deg": ra_deg, "dec_deg": dec_deg}
    frame_records = []
    for frame_id, row in frames.items():
        image, bad, footprint = projected[frame_id]
        png = f"{frame_id}.png"
        mask = f"mask/{frame_id}.png"
        render.to_png(image, bad, stretches[row["detector"]], outdir / png,
                      footprint=footprint)
        render.mask_png(bad, footprint, outdir / mask)
        frame_records.append({
            "id": frame_id, "png": png, "mask_png": mask,
            "obs_time_utc": row["obs_time_utc"],
            "width_px": int(image.shape[1]), "height_px": int(image.shape[0]),
            "mjd": float(row["mjd"]), "survey_pass": int(row["survey_pass"]),
            "detector": int(row["detector"]), "wavelength_um": float(row["wavelength_um"]),
            "center": center, "bad_pixel_fraction": float(row["bad_pixel_fraction"]),
            "stretch": stretches[row["detector"]], "source_url": row["source_url"],
            "obs_id": row["obs_id"], "processing_version": str(row["processing_version"]),
            "collection": str(row["collection"]),
            "downloaded_utc": _downloaded_utc(str(row["downloaded_utc"])),
        })
    for pair in pairs:
        a, b = pair["a"], pair["b"]
        first, bad_a, _ = projected[a]
        second, bad_b, _ = projected[b]
        noise = np.hypot(float(frames[a]["noise_mad_mjysr"]), float(frames[b]["noise_mad_mjysr"]))
        diff_png = f"diff/{a}-{b}.png"
        (outdir / "diff").mkdir(exist_ok=True)
        render.diff_png(first, second, bad_a | bad_b, outdir / diff_png, float(noise))
        pair["diff_png"] = diff_png
    best = pairs[0]["a"]
    image, bad, footprint = projected[best]
    render.to_png(image, bad, stretches[frames[best]["detector"]], outdir / "thumb.png",
                  scale=2, footprint=footprint)
    manifest = {
        "schema_version": "1.1", "field_id": field_id, "kind": "static",
        "title": field["title"], "description": field["description"],
        "center": center, "size_arcmin": size_arcmin, "pixel_scale_arcsec": 6.15,
        "frames": frame_records, "pairs": pairs,
        "provenance": {
            "mission": "SPHEREx", "archive": "NASA/IPAC IRSA",
            "collections": sorted({str(row["collection"]) for row in frames.values()}),
            "doi": str(field.get("doi", "")),
            "downloaded_utc": max(_downloaded_utc(value) for value in downloads),
            "pipeline_commit": _commit(), "cached": True, "synthetic": synthetic,
        },
    }
    write_field(manifest, outdir, real_build=not synthetic)
    timeline = [
        {"frame_id": frame["id"], "obs_time_utc": frame["obs_time_utc"], "mjd": frame["mjd"]}
        for frame in sorted(
            frame_records,
            key=lambda item: (datetime.fromisoformat(item["obs_time_utc"].replace("Z", "+00:00")),
                              item["id"]),
        )
    ]
    temporary = outdir / "timeline.json.tmp"
    temporary.write_text(json.dumps(timeline, indent=2, allow_nan=False) + "\n")
    temporary.replace(outdir / "timeline.json")
    update_index(data_root)
    counts = Counter(pair["trust"] for pair in pairs)
    mb = sum(path.stat().st_size for path in outdir.iterdir() if path.is_file()) / 1_000_000
    print(f"{field_id}: {len(frames)}/{len(epochs)} frames, {len(set(passes) - {0})} passes, "
          f"pairs high={counts['high']} medium={counts['medium']} low={counts['low']}, {mb:.2f} MB")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--max-frames", type=int)
    args = parser.parse_args()
    build_field(args.id, offline=args.offline, max_frames=args.max_frames)


if __name__ == "__main__":
    main()
