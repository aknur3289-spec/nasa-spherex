"""Python implementation of the static field contract in docs/CONTRACT.md."""
from __future__ import annotations

import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_ID = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
_ASSET = re.compile(r"^(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.(?:png|fits)$")
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _positive(value: Any) -> bool:
    return _finite(value) and value > 0


def _natural(value: Any) -> bool:
    return _finite(value) and value >= 0 and int(value) == value


def _utc(value: Any) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z", value):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
        return True
    except ValueError:
        return False


def _center(value: Any) -> bool:
    return (isinstance(value, dict) and _finite(value.get("ra_deg")) and
            0 <= value["ra_deg"] < 360 and _finite(value.get("dec_deg")) and
            -90 <= value["dec_deg"] <= 90)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _asset_ok(value: Any, suffix: str | None = None) -> bool:
    return isinstance(value, str) and bool(_ASSET.fullmatch(value)) and (suffix is None or value.lower().endswith(suffix))


def validate_field(field: dict, field_dir: str | Path | None = None) -> list[str]:
    """Return all detectable contract errors. PNGs are checked in out/<field_id>."""
    errors: list[str] = []
    def err(message: str) -> None:
        errors.append(message)

    if not isinstance(field, dict):
        return ["field must be an object"]
    required = ("schema_version", "field_id", "kind", "title", "description", "center", "size_arcmin",
                "pixel_scale_arcsec", "frames", "pairs", "provenance")
    for key in required:
        if key not in field: err(f"missing field key: {key}")
    fid = field.get("field_id")
    asset_dir = Path(field_dir) if field_dir is not None else (_REPO_ROOT / "out" / str(fid))
    if not isinstance(fid, str) or not _ID.fullmatch(fid):
        err("field_id is not a valid lowercase ID")
    elif asset_dir.name != fid or not asset_dir.is_dir():
        err("field_id must match its out/ directory")
    if field.get("schema_version") != "1.0": err("schema_version must be 1.0")
    if field.get("kind") not in ("static", "dial"): err("kind must be static or dial")
    for key in ("title", "description"):
        if not _nonempty(field.get(key)): err(f"{key} must be a nonempty string")
    if not _center(field.get("center")): err("invalid field center")
    for key in ("size_arcmin", "pixel_scale_arcsec"):
        if not _positive(field.get(key)): err(f"{key} must be positive and finite")

    p = field.get("provenance")
    prov_keys = ("mission", "archive", "collections", "doi", "downloaded_utc", "pipeline_commit", "cached", "synthetic")
    if not isinstance(p, dict):
        err("provenance must be an object"); p = {}
    for key in prov_keys:
        if key not in p: err(f"missing provenance key: {key}")
    for key in ("mission", "archive", "doi", "pipeline_commit"):
        if not _nonempty(p.get(key)): err(f"provenance.{key} must be a nonempty string")
    if not _utc(p.get("downloaded_utc")): err("provenance.downloaded_utc must be an ISO timestamp ending in Z")
    if not isinstance(p.get("collections"), list) or not p.get("collections") or not all(_nonempty(x) for x in p.get("collections", [])):
        err("provenance.collections must be a nonempty array of strings")
    for key in ("cached", "synthetic"):
        if not isinstance(p.get(key), bool): err(f"provenance.{key} must be boolean")

    frames = field.get("frames")
    if not isinstance(frames, list): err("frames must be an array"); frames = []
    frame_ids: set[str] = set()
    for i, f in enumerate(frames):
        label = f"frames[{i}]"
        if not isinstance(f, dict): err(f"{label} must be an object"); continue
        keys = ("id", "png", "obs_time_utc", "mjd", "survey_pass", "detector", "wavelength_um", "center",
                "bad_pixel_fraction", "stretch", "source_url", "obs_id", "processing_version")
        for key in keys:
            if key not in f: err(f"{label} missing key: {key}")
        frame_id = f.get("id")
        if not isinstance(frame_id, str) or not _ID.fullmatch(frame_id): err(f"{label}.id is invalid")
        elif frame_id in frame_ids: err(f"duplicate frame ID: {frame_id}")
        else: frame_ids.add(frame_id)
        png = f.get("png")
        if not _asset_ok(png, ".png"):
            err(f"{label}.png must be a safe relative PNG path")
        elif isinstance(fid, str) and _ID.fullmatch(fid):
            png_path = asset_dir / png
            if not png_path.is_file():
                err(f"{label}.png does not exist")
            elif not png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                err(f"{label}.png is not a PNG file")
        fits = f.get("fits")
        if fits is not None and not _asset_ok(fits, ".fits"): err(f"{label}.fits must be a safe relative FITS path")
        if not _utc(f.get("obs_time_utc")): err(f"{label}.obs_time_utc must end in Z")
        if not _finite(f.get("mjd")): err(f"{label}.mjd must be finite")
        for key in ("survey_pass", "detector"):
            if not _natural(f.get(key)): err(f"{label}.{key} must be a nonnegative integer")
        if f.get("band") is not None and not _nonempty(f.get("band")): err(f"{label}.band must be nonempty")
        if not _positive(f.get("wavelength_um")): err(f"{label}.wavelength_um must be positive")
        if not _center(f.get("center")): err(f"{label}.center is invalid")
        bpf = f.get("bad_pixel_fraction")
        if not _finite(bpf) or not 0 <= bpf <= 1: err(f"{label}.bad_pixel_fraction must be in [0, 1]")
        st = f.get("stretch")
        if not isinstance(st, dict) or st.get("kind") != "asinh" or not _finite(st.get("lo")) or not _finite(st.get("hi")) or st.get("lo", 0) >= st.get("hi", 0) or not _nonempty(st.get("unit")):
            err(f"{label}.stretch must have kind asinh, finite lo < hi, and a unit")
        source = f.get("source_url")
        synthetic = p.get("synthetic") is True
        try:
            parsed_source = urlparse(source) if isinstance(source, str) else None
            valid_source = (parsed_source is not None and parsed_source.scheme == "https" and
                            bool(parsed_source.hostname) and parsed_source.username is None and
                            parsed_source.password is None and
                            ((parsed_source.hostname == "example.invalid") == synthetic))
        except ValueError:
            valid_source = False
        if not valid_source:
            err(f"{label}.source_url must be HTTPS and match synthetic provenance")
        for key in ("obs_id", "processing_version"):
            if not _nonempty(f.get(key)): err(f"{label}.{key} must be nonempty")
    if len(frame_ids) != len(frames):
        pass

    pairs = field.get("pairs")
    if not isinstance(pairs, list): err("pairs must be an array"); pairs = []
    for i, pair in enumerate(pairs):
        label = f"pairs[{i}]"
        if not isinstance(pair, dict): err(f"{label} must be an object"); continue
        for key in ("a", "b", "dlambda_frac", "dt_days", "trust"):
            if key not in pair: err(f"{label} missing key: {key}")
        a, b = pair.get("a"), pair.get("b")
        if a not in frame_ids or b not in frame_ids or a == b: err(f"{label} endpoints must be distinct frame IDs")
        dl, dt = pair.get("dlambda_frac"), pair.get("dt_days")
        if not _finite(dl) or dl < 0: err(f"{label}.dlambda_frac must be nonnegative")
        if not _finite(dt) or dt < 0: err(f"{label}.dt_days must be nonnegative")
        expected = "high" if _finite(dl) and dl <= .02 else "medium" if _finite(dl) and dl <= .05 else "low"
        if pair.get("trust") != expected: err(f"{label}.trust is inconsistent with dlambda_frac")

    dial = field.get("dial")
    if field.get("kind") == "dial" and dial is None: err("dial metadata is required for dial fields")
    if dial is not None:
        if not isinstance(dial, dict): err("dial must be an object"); dial = {}
        for key in ("reference_frame", "model", "search_radius_px", "steps", "peak_distance_au", "truth", "negative_control_field"):
            if key not in dial: err(f"dial missing key: {key}")
        if dial.get("reference_frame") not in frame_ids: err("dial.reference_frame must exist in frames")
        if not _nonempty(dial.get("model")): err("dial.model must be nonempty")
        if not _positive(dial.get("search_radius_px")): err("dial.search_radius_px must be positive")
        if not _positive(dial.get("peak_distance_au")): err("dial.peak_distance_au must be positive")
        truth = dial.get("truth")
        if not isinstance(truth, dict) or not _positive(truth.get("distance_au")) or not _nonempty(truth.get("source")):
            err("dial.truth must have positive distance_au and nonempty source")
        nc = dial.get("negative_control_field")
        if not isinstance(nc, str) or not _ID.fullmatch(nc): err("dial.negative_control_field must be a valid ID")
        steps = dial.get("steps")
        if not isinstance(steps, list): err("dial.steps must be an array"); steps = []
        for i, step in enumerate(steps):
            label = f"dial.steps[{i}]"
            if not isinstance(step, dict): err(f"{label} must be an object"); continue
            for key in ("distance_au", "frame", "pred", "snr", "offset_px"):
                if key not in step: err(f"{label} missing key: {key}")
            if not _positive(step.get("distance_au")): err(f"{label}.distance_au must be positive")
            if step.get("frame") not in frame_ids: err(f"{label}.frame must exist in frames")
            if not _center(step.get("pred")): err(f"{label}.pred is invalid")
            if not _finite(step.get("snr")): err(f"{label}.snr must be finite")
            if not _finite(step.get("offset_px")) or step.get("offset_px", -1) < 0: err(f"{label}.offset_px must be finite and nonnegative")
    return errors
