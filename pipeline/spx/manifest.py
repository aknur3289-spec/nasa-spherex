"""Validate and write version 1.0 static field manifests."""

from __future__ import annotations

import json
import math
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator

from .pairs import trust_of

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema/field_v1.schema.json"


def validate_field(field: dict, outdir: Path | None = None, *, real_build: bool = False) -> None:
    """Reject schema, reference, asset, and provenance errors with JSON paths."""
    schema = json.loads(SCHEMA_PATH.read_text())
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
        if outdir is not None and not (outdir / frame["png"]).is_file():
            raise ValueError(f"{prefix}.png: missing asset {frame['png']}")
    for index, pair in enumerate(field["pairs"]):
        prefix = f"$.pairs[{index}]"
        if pair["a"] == pair["b"] or pair["a"] not in ids or pair["b"] not in ids:
            raise ValueError(f"{prefix}: endpoints must be distinct existing frames")
        if not all(math.isfinite(pair[key]) for key in ("dlambda_frac", "dt_days")):
            raise ValueError(f"{prefix}: pair metrics must be finite")
        if pair["trust"] != trust_of(pair["dlambda_frac"]):
            raise ValueError(f"{prefix}.trust: inconsistent with dlambda_frac")
    if field["kind"] == "dial":
        dial = field["dial"]
        if dial["reference_frame"] not in ids or any(step["frame"] not in ids for step in dial["steps"]):
            raise ValueError("$.dial: referenced frame is missing")


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
