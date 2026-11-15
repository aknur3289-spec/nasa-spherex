"""Build offline three-band field composites from cached calibrated FITS frames."""

from __future__ import annotations

import argparse
import csv
import json
import warnings
from pathlib import Path

import numpy as np
from PIL import Image

from pipeline.spx.frame import read_frame
from pipeline.spx.manifest import write_field
from pipeline.spx import render


BANDS = {
    "m101": ((1.10, 1.55), (1.55, 1.85), (1.85, 2.42)),
    "nep": ((0.75, 1.10), (1.10, 1.70), (1.70, 2.42)),
    "ecl": ((0.75, 1.10), (1.10, 1.70), (1.70, 2.42)),
    "neptune-track": ((0.75, 1.10), (1.10, 1.70), (1.70, 2.42)),
}


def compose(bands: list[list[np.ndarray]]) -> np.ndarray:
    """Median each wavelength bin, then apply one common asinh intensity mapping."""
    if len(bands) != 3 or any(not group for group in bands):
        raise ValueError("a composite needs three nonempty wavelength bins")
    medians = []
    for group in bands:
        if len({image.shape for image in group}) != 1:
            raise ValueError("all images in a bin must share the field grid")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            medians.append(np.nanmedian(np.stack(group), axis=0))
    if len({image.shape for image in medians}) != 1:
        raise ValueError("all bins must share the field grid")
    cube = np.stack(medians)
    finite = cube[np.isfinite(cube)]
    if not finite.size:
        raise ValueError("composite has no valid pixels")
    lo, hi = np.percentile(finite, (5, 99.7))
    if not lo < hi:
        raise ValueError("composite has no contrast")
    clipped = np.clip((cube - lo) / (hi - lo), 0, 1)
    mapped = np.arcsinh(10 * clipped) / np.arcsinh(10)
    rgb = np.rint(np.nan_to_num(mapped[[2, 1, 0]], nan=0) * 255).astype(np.uint8)
    alpha = np.where(np.all(np.isfinite(cube), axis=0), 255, 0).astype(np.uint8)
    return np.dstack((np.moveaxis(rgb, 0, -1), alpha))


def build_color(field_id: str, root: Path = Path("web/public/data")) -> list[int]:
    outdir = root / field_id
    manifest = json.loads((outdir / "field.json").read_text())
    limits = BANDS[field_id]
    if field_id == "neptune-track":
        source = Path("data/meta/neptune/epochs.csv")
        rows = {row["obs_id"]: row for row in csv.DictReader(source.open())}
    else:
        source = Path(f"data/meta/{field_id}/epochs.csv")
        rows = {row["frame_id"]: row for row in csv.DictReader(source.open())}
    center = manifest["center"]
    grid, shape = render.field_grid(center["ra_deg"], center["dec_deg"], manifest["size_arcmin"])
    groups: list[list[np.ndarray]] = [[], [], []]
    counts = [0, 0, 0]
    for record in manifest["frames"]:
        group = next((i for i, (lo, hi) in enumerate(limits)
                      if lo <= record["wavelength_um"] < hi), None)
        if group is None:
            continue
        key = record["obs_id"] if field_id == "neptune-track" else record["id"]
        row = rows[key]
        target = record.get("target_radec", center)
        frame = read_frame(Path(row["local_path"]), target["ra_deg"], target["dec_deg"])
        values, bad, footprint = render.to_grid_with_footprint(frame, grid, shape)
        valid = ~bad & np.isfinite(values) & footprint
        if not valid.any():
            raise ValueError(f"{field_id}/{record['id']}: no valid pixels")
        display = render._fill_display_only(np.where(valid, values, np.nan), footprint & ~valid)
        display -= np.median(values[valid])
        display[~footprint] = np.nan
        groups[group].append(display)
        counts[group] += 1
    if min(counts) == 0:
        raise ValueError(f"{field_id}: missing wavelength bin: {counts}")
    Image.fromarray(compose(groups), mode="RGBA").save(outdir / "color.png")
    manifest["color_png"] = "color.png"
    manifest["color_bands_um"] = [list(pair) for pair in limits]
    write_field(manifest, outdir, real_build=True)
    print(f"{field_id}: " + ", ".join(
        f"{lo:.2f}–{hi:.2f} um: {count} frames"
        for (lo, hi), count in zip(limits, counts)))
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("fields", nargs="*", choices=tuple(BANDS))
    args = parser.parse_args()
    for name in args.fields or BANDS:
        build_color(name)
