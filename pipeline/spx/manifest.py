"""Validate and write versioned static field manifests."""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator
from PIL import Image

from .pairs import trust_of

SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "schema"
SCHEMA_PATHS = {
    "1.0": SCHEMA_ROOT / "field_v1.schema.json",
    "1.1": SCHEMA_ROOT / "field_v1_1.schema.json",
}


def validate_field(field: dict, outdir: Path | None = None, *, real_build: bool = False) -> None:
    """Reject schema, reference, asset, and provenance errors with JSON paths."""
    version = field.get("schema_version")
    if version not in SCHEMA_PATHS:
        raise ValueError("$.schema_version: unsupported version")
    schema = json.loads(SCHEMA_PATHS[version].read_text())
    error = next(iter(Draft202012Validator(schema).iter_errors(field)), None)
    if error:
        path = "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.path)
        raise ValueError(f"{path}: {error.message}")
    if real_build and field["provenance"]["synthetic"]:
        raise ValueError("$.provenance.synthetic: real build cannot be synthetic")
    ids: set[str] = set()
    for index, frame in enumerate(field["frames"]):
        prefix = f"$.frames[{index}]"
        if frame["id"] in ids:
            raise ValueError(f"{prefix}.id: duplicate frame ID")
        ids.add(frame["id"])
        for key in ("mjd", "wavelength_um", "bad_pixel_fraction"):
            if not math.isfinite(frame[key]):
                raise ValueError(f"{prefix}.{key}: must be finite")
        stretch = frame["stretch"]
        if not all(math.isfinite(stretch[key]) for key in ("lo", "hi")) or stretch["lo"] >= stretch["hi"]:
            raise ValueError(f"{prefix}.stretch: finite lo must be below hi")
        url = urlparse(frame["source_url"])
        if not field["provenance"]["synthetic"] and (url.scheme != "https" or url.netloc == "example.invalid"):
            raise ValueError(f"{prefix}.source_url: real frame needs an HTTPS source")
        if not field["provenance"]["synthetic"]:
            for key in ("collection", "downloaded_utc"):
                if not frame.get(key):
                    raise ValueError(f"{prefix}.{key}: real frame needs provenance")
            release = frame["collection"]
            if release not in {"spherex_dr1", "spherex_qr3"} or f"/spherex/{release.removeprefix('spherex_')}/" not in url.path:
                raise ValueError(f"{prefix}.collection: must match source_url release")
            try:
                downloaded = datetime.fromisoformat(
                    frame["downloaded_utc"].replace("Z", "+00:00")
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{prefix}.downloaded_utc: invalid UTC time") from exc
            if downloaded.utcoffset() is None or downloaded.utcoffset().total_seconds() != 0:
                raise ValueError(f"{prefix}.downloaded_utc: must be UTC")
        if outdir is not None and not (outdir / frame["png"]).is_file():
            raise ValueError(f"{prefix}.png: missing asset {frame['png']}")
        if version == "1.1" and outdir is not None:
            with Image.open(outdir / frame["png"]) as image:
                if image.size != (frame["width_px"], frame["height_px"]):
                    raise ValueError(f"{prefix}.png: dimensions differ from frame metadata")
    for index, pair in enumerate(field["pairs"]):
        prefix = f"$.pairs[{index}]"
        if pair["a"] == pair["b"] or pair["a"] not in ids or pair["b"] not in ids:
            raise ValueError(f"{prefix}: endpoints must be distinct existing frames")
        if not all(math.isfinite(pair[key]) for key in ("dlambda_frac", "dt_days")):
            raise ValueError(f"{prefix}: pair metrics must be finite")
        if pair["trust"] != trust_of(pair["dlambda_frac"]):
            raise ValueError(f"{prefix}.trust: inconsistent with dlambda_frac")
        if "diff_png" in pair and outdir is not None:
            path = outdir / pair["diff_png"]
            if not path.is_file():
                raise ValueError(f"{prefix}.diff_png: missing asset {pair['diff_png']}")
            with Image.open(path) as image:
                frame = next(frame for frame in field["frames"] if frame["id"] == pair["a"])
                if image.size != (frame["width_px"], frame["height_px"]):
                    raise ValueError(f"{prefix}.diff_png: dimensions differ from frame")
    if field["kind"] == "dial":
        dial = field["dial"]
        if dial["reference_frame"] not in ids or any(step["frame"] is not None and step["frame"] not in ids for step in dial["steps"]):
            raise ValueError("$.dial: referenced frame is missing")
        for index, step in enumerate(dial["steps"]):
            outside = step.get("outside_frame", False)
            empty = all(step[key] is None for key in ("frame", "snr", "offset_px"))
            full = all(step[key] is not None for key in ("frame", "snr", "offset_px"))
            if not (outside and empty or not outside and full):
                raise ValueError(f"$.dial.steps[{index}]: outside step must have null measurements; covered step must have measurements")
        distances = [step["distance_au"] for step in dial["steps"]]
        if distances != sorted(distances) or len(set(distances)) != len(distances):
            raise ValueError("$.dial.steps: distances must be unique and ascending")
        covered = [step for step in dial["steps"] if step["offset_px"] is not None]
        if not covered or dial["peak_distance_au"] != min(covered, key=lambda step: step["offset_px"])["distance_au"]:
            raise ValueError("$.dial.peak_distance_au: must match the minimum covered offset")


def write_field(field: dict, outdir: Path, *, real_build: bool = False) -> None:
    """Validate and atomically write a deterministic field.json."""
    if field.get("field_id") != outdir.name:
        raise ValueError("$.field_id: must match output directory")
    validate_field(field, outdir, real_build=real_build)
    outdir.mkdir(parents=True, exist_ok=True)
    temporary = outdir / "field.json.tmp"
    temporary.write_text(json.dumps(field, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(outdir / "field.json")


def update_index(data_root: Path) -> None:
    """Rebuild index.json from field manifests with existing thumbnails."""
    entries = []
    for path in sorted(data_root.glob("*/field.json")):
        field = json.loads(path.read_text())
        if field["provenance"]["synthetic"]:
            continue
        if field["field_id"] != path.parent.name:
            raise ValueError(f"{path}: field_id does not match directory")
        thumbnail = "thumb.png" if (path.parent / "thumb.png").is_file() else field["frames"][0]["png"]
        entries.append({"field_id": field["field_id"], "kind": field["kind"],
                        "title": field["title"], "thumbnail": f"{path.parent.name}/{thumbnail}"})
    data_root.mkdir(parents=True, exist_ok=True)
    temporary = data_root / "index.json.tmp"
    temporary.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n")
    temporary.replace(data_root / "index.json")
