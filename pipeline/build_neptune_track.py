"""Build a fixed-sky Neptune timelapse from cached Horizons-centred cutouts."""

from __future__ import annotations

import csv
import json
import math
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

from pipeline.build_field import _pairs
from pipeline.spx.frame import read_frame
from pipeline.spx.manifest import update_index, write_field
from pipeline.spx.pairs import assign_survey_pass, match_pairs, naive_pairs
from pipeline.spx import render

EPOCHS = Path("data/meta/neptune/epochs.csv")
DATA_ROOT = Path("web/public/data")
SIZE_ARCMIN = 10.0


def _mean_ra_deg(rows: list[dict]) -> float:
    angles = np.deg2rad([float(row["eph_ra"]) for row in rows])
    return float(np.rad2deg(np.angle(np.mean(np.exp(1j * angles)))) % 360)


def longest_fixed_window(rows: list[dict], size_arcmin: float = SIZE_ARCMIN) -> list[dict]:
    """Choose the longest chronological run whose target positions fit one square."""
    ordered = sorted(rows, key=lambda row: float(row["mjd"]))
    best: list[dict] = []
    for start in range(len(ordered)):
        for stop in range(start + 1, len(ordered) + 1):
            segment = ordered[start:stop]
            center_ra = _mean_ra_deg(segment)
            center_dec = float(np.mean([float(row["eph_dec"]) for row in segment]))
            within = all(
                abs(((float(row["eph_ra"]) - center_ra + 180) % 360 - 180)
                    * math.cos(math.radians(center_dec)) * 60) <= size_arcmin / 2
                and abs((float(row["eph_dec"]) - center_dec) * 60) <= size_arcmin / 2
                for row in segment
            )
            if within and len(segment) > len(best):
                best = segment
            elif not within:
                break
    if not best:
        raise ValueError("no Neptune exposures fit a fixed sky grid")
    return best


def build_neptune_track(
    epochs_path: Path = EPOCHS, data_root: Path = DATA_ROOT
) -> dict:
    """Read only cached FITS, render a fixed grid, and write a real field manifest."""
    with epochs_path.open(newline="") as source:
        all_rows = list(csv.DictReader(source))
    if not all_rows or len({row["obs_id"] for row in all_rows}) != len(all_rows):
        raise ValueError("Neptune exposures must have unique obs_id values")
    for row in all_rows:
        if row["status"] != "ok" or not Path(row["local_path"]).is_file():
            raise ValueError(f"missing cached Neptune exposure: {row['obs_id']}")
    window = longest_fixed_window(all_rows)
    center = {
        "ra_deg": _mean_ra_deg(window),
        "dec_deg": float(np.mean([float(row["eph_dec"]) for row in window])),
    }
    grid_wcs, shape = render.field_grid(center["ra_deg"], center["dec_deg"], SIZE_ARCMIN)
    selected = []
    for row in window:
        ra_deg, dec_deg = float(row["eph_ra"]), float(row["eph_dec"])
        frame = read_frame(Path(row["local_path"]), ra_deg, dec_deg)
        if frame.meta["status"] != "ok" or frame.meta["target_bad"]:
            continue
        image, bad, footprint = render.to_grid_with_footprint(frame, grid_wcs, shape)
        target_x, target_y = grid_wcs.world_to_pixel_values(ra_deg, dec_deg)
        x, y = round(float(target_x)), round(float(target_y))
        if not (0 <= x < shape[1] and 0 <= y < shape[0] and footprint[y, x] and not bad[y, x]):
            continue
        selected.append((row, frame, image, bad, footprint))
    if not selected:
        raise ValueError("no usable Neptune frames in fixed window")

    frame_rows = []
    for number, (row, frame, _, _, _) in enumerate(selected, 1):
        source_url = row["access_url"]
        if "/spherex/dr1/" in source_url:
            collection = "spherex_dr1"
        elif "/spherex/qr3/" in source_url:
            collection = "spherex_qr3"
        else:
            raise ValueError(f"unknown archive release: {source_url}")
        frame_rows.append({
            "frame_id": f"f{number:03d}", "obs_id": row["obs_id"],
            "mjd": frame.meta["mjd"], "detector": frame.meta["detector"],
            "collection": collection,
            "wavelength_um": frame.meta["wavelength_um"],
            "bad_pixel_fraction": frame.meta["bad_pixel_fraction"],
            "target_bad": frame.meta["target_bad"], "status": frame.meta["status"],
        })
    pair_input = pd.DataFrame(frame_rows)
    pair_input["survey_pass"] = assign_survey_pass(pair_input["mjd"].to_numpy(dtype=float))
    pairs = _pairs(match_pairs(pair_input), naive_pairs(pair_input))

    outdir = data_root / "neptune-track"
    outdir.mkdir(parents=True, exist_ok=True)
    projected = {}
    frame_records = []
    stretches = {
        detector: render.stretch_params([
            selected[index][2] for index, item in enumerate(frame_rows)
            if item["detector"] == detector
        ])
        for detector in sorted(pair_input["detector"].unique())
    }
    for item, (row, frame, image, bad, footprint) in zip(frame_rows, selected):
        frame_id = item["frame_id"]
        png, mask = f"{frame_id}.png", f"mask/{frame_id}.png"
        render.to_png(image, bad, stretches[item["detector"]], outdir / png,
                      footprint=footprint)
        render.mask_png(bad, footprint, outdir / mask)
        projected[frame_id] = (image, bad, frame.meta["noise_mad_mjysr"])
        downloaded_utc = datetime.fromtimestamp(
            Path(row["local_path"]).stat().st_mtime, timezone.utc
        ).isoformat().replace("+00:00", "Z")
        frame_records.append({
            "id": frame_id, "png": png, "mask_png": mask,
            "obs_time_utc": frame.meta["obs_time_utc"],
            "mjd": frame.meta["mjd"], "survey_pass": int(pair_input.iloc[len(frame_records)]["survey_pass"]),
            "detector": item["detector"], "wavelength_um": item["wavelength_um"],
            "center": center,
            "target_radec": {"ra_deg": float(row["eph_ra"]), "dec_deg": float(row["eph_dec"])},
            "bad_pixel_fraction": item["bad_pixel_fraction"],
            "stretch": stretches[item["detector"]],
            "source_url": row["access_url"], "obs_id": row["obs_id"],
            "processing_version": frame.meta["processing_version"],
            "collection": item["collection"],
            "downloaded_utc": downloaded_utc,
            "width_px": shape[1], "height_px": shape[0],
        })
    for pair in pairs:
        first, bad_a, noise_a = projected[pair["a"]]
        second, bad_b, noise_b = projected[pair["b"]]
        path = f"diff/{pair['a']}-{pair['b']}.png"
        render.diff_png(first, second, bad_a | bad_b, outdir / path,
                        float(np.hypot(noise_a, noise_b)))
        pair["diff_png"] = path
    first = frame_records[0]
    _, _, image, bad, footprint = selected[0]
    render.to_png(image, bad, stretches[first["detector"]], outdir / "thumb.png",
                  scale=2, footprint=footprint)
    doi = yaml.safe_load(Path("pipeline/fields.yaml").read_text())["defaults"]["doi"]
    manifest = {
        "schema_version": "1.1", "field_id": "neptune-track", "kind": "static",
        "title": "Neptune against fixed stars",
        "description": "Neptune moving against fixed stars; known planet, not a discovery. Fixed 10′ sky grid in June–early July 2025; this short window has no 150-day wavelength-matched pairs.",
        "center": center, "size_arcmin": SIZE_ARCMIN, "pixel_scale_arcsec": 6.15,
        "frames": frame_records, "pairs": pairs,
        "provenance": {
            "mission": "SPHEREx", "archive": "NASA/IPAC IRSA",
            "collections": sorted({frame["collection"] for frame in frame_records}),
            "doi": doi,
            "downloaded_utc": max(frame["downloaded_utc"] for frame in frame_records),
            "pipeline_commit": subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], text=True
            ).strip(),
            "cached": True, "synthetic": False,
        },
    }
    write_field(manifest, outdir, real_build=True)
    timeline = [
        {"frame_id": frame["id"], "obs_time_utc": frame["obs_time_utc"], "mjd": frame["mjd"]}
        for frame in sorted(frame_records, key=lambda item: item["mjd"])
    ]
    (outdir / "timeline.json").write_text(json.dumps(timeline, indent=2) + "\n")
    update_index(data_root)
    counts = Counter(pair["trust"] for pair in pairs)
    print(f"neptune-track: {len(frame_records)}/{len(window)} window exposures, "
          f"pairs high={counts['high']} medium={counts['medium']} low={counts['low']}, "
          f"MJD {window[0]['mjd']}–{window[-1]['mjd']}")
    return manifest


if __name__ == "__main__":
    build_neptune_track()
