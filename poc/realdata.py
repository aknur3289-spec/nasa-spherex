"""Temporary SPHEREx access helpers for PoC B.

These minimal helpers are a stopgap; the teammate-owned pipeline/spx/io.py is
intended to replace them. They query IRSA SIA2 and read bounded image sections.
"""
from __future__ import annotations

import hashlib
import io
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
import xml.etree.ElementTree as ET

import numpy as np
import pyvo
import requests
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import astropy.units as u

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SIA_URL = "https://irsa.ipac.caltech.edu/SIA?"
_frames_cache: dict[tuple, list[dict]] = {}
_collections: list[str] | None = None
_reported_hdu_sets: set[tuple[str, ...]] = set()
_local_by_obs: dict[str, Path | None] = {}
_section_index_loaded = False
_section_index: dict[tuple[str, str], list[Path]] = {}


def spherex_collections() -> list[str]:
    """Read supported SPHEREx collection values from IRSA SIA2 metadata."""
    global _collections
    if _collections is None:
        service = pyvo.dal.SIA2Service(SIA_URL)
        url = service.query_ep.rstrip("?") + "/queryables?MAXREC=0"
        with urlopen(url) as response:
            root = ET.fromstring(response.read())
        values = []
        for param in root.iter():
            if param.tag.endswith("PARAM") and param.attrib.get("name", "").upper() == "COLLECTION":
                for values_el in param:
                    if values_el.tag.endswith("VALUES"):
                        values.extend(option.attrib["value"] for option in values_el
                                      if option.tag.endswith("OPTION") and "value" in option.attrib)
        _collections = sorted({v for v in values if v.lower().startswith("spherex") and "_cube" not in v.lower()})
        print("IRSA SIA2 SPHEREx collections (excluding cube products):", _collections)
    return _collections


def sia_frames(ra, dec, radius_deg, t_start, t_end) -> list[dict]:
    """Query all non-cube SPHEREx collections, retaining single science exposures."""
    key = (round(float(ra), 8), round(float(dec), 8), float(radius_deg), str(t_start), str(t_end))
    if key in _frames_cache:
        return _frames_cache[key]
    service = pyvo.dal.SIA2Service(SIA_URL)
    coord = SkyCoord(float(ra) * u.deg, float(dec) * u.deg)
    rows = []
    for collection in spherex_collections():
        table = service.search(pos=(coord, float(radius_deg) * u.deg),
                               time=(str(t_start), str(t_end)), collection=collection).to_table()
        for row in table.to_pandas().to_dict("records"):
            if (row.get("algorithm_name") == "exposure"
                    and str(row.get("dataproduct_subtype", "")).lower() == "science"
                    and "_cube" not in str(row.get("obs_collection", "")).lower()):
                rows.append(row)
    # Distinct cutout targets may refer to same image through overlapping collection values.
    unique = {row.get("access_url"): row for row in rows}
    result = list(unique.values())
    _frames_cache[key] = result
    return result


def cutout(access_url, ra, dec, size_deg):
    """Fetch/cache an IRSA cutout. Never falls back to the full access_url."""
    RAW.mkdir(parents=True, exist_ok=True)
    query = urlencode({"center": f"{float(ra):.10f},{float(dec):.10f}", "size": f"{float(size_deg):.8f}"})
    url = f"{access_url}{'&' if '?' in access_url else '?'}{query}"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    path = RAW / f"{digest}.fits"
    if path.exists():
        return path
    last_error = None
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=120)
            if not response.ok:
                detail = response.text[:1000]
                raise RuntimeError(f"HTTP {response.status_code} {response.reason}; response body: {detail!r}")
            if not response.content.startswith(b"SIMPLE"):
                raise RuntimeError(f"HTTP {response.status_code} returned a non-FITS cutout body: {response.content[:200]!r}")
            path.write_bytes(response.content)
            return path
        except Exception as exc:
            last_error = exc
            print(f"cutout attempt {attempt + 1}/3 failed: {exc!r}")
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"cutout failed after 3 attempts: {last_error!r}") from last_error


def read_cutout(path):
    """Return (IMAGE MJy/sr, FLAGS, celestial WCS, center wavelength in micron)."""
    with fits.open(path, memmap=False) as hdul:
        names = [h.name for h in hdul]
        signature = tuple(names)
        if signature not in _reported_hdu_sets:
            print("FITS extension names:", names)
            _reported_hdu_sets.add(signature)
        image_hdu, flags_hdu = hdul["IMAGE"], hdul["FLAGS"]
        image = np.array(image_hdu.data, dtype=float, copy=True)
        flags = np.array(flags_hdu.data, copy=True)
        wcs = WCS(image_hdu.header, fobj=hdul).celestial
        wave = None
        if "WCS-WAVE" in hdul:
            wave_wcs = WCS(image_hdu.header, fobj=hdul)
            try:
                world = wave_wcs.pixel_to_world((image.shape[1] - 1) / 2, (image.shape[0] - 1) / 2)
                if isinstance(world, tuple):
                    for item in world:
                        if hasattr(item, "unit") and item.unit is not None and item.unit.is_equivalent(u.m):
                            wave = item.to_value(u.um)
                            break
                elif hasattr(world, "spectral"):
                    wave = world.spectral.to_value(u.um)
            except Exception as exc:
                print(f"spectral WCS evaluation failed: {exc!r}")
        if wave is None:
            # Follow the IRSA WCS-WAVE table convention: X/Y control points and
            # VALUES=(central wavelength, bandwidth), bilinearly interpolated.
            table = hdul["WCS-WAVE"].data
            x, y, vals = table["X"][0], table["Y"][0], table["VALUES"][0]
            cx, cy = (image.shape[1] - 1) / 2, (image.shape[0] - 1) / 2
            ix = np.argsort(np.abs(np.asarray(x, float) - cx))[:2]
            iy = np.argsort(np.abs(np.asarray(y, float) - cy))[:2]
            pts = [(float(x[j]), float(y[i]), float(vals[i, j, 0])) for i in iy for j in ix]
            # Inverse-distance interpolation at centre, in FITS pixel coordinates.
            weights = np.array([1 / max((px-cx)**2 + (py-cy)**2, 1e-12) for px, py, _ in pts])
            wave = float(np.average([v for _, _, v in pts], weights=weights))
        return image, flags, wcs, float(wave) if wave is not None else None


def stamp(image, wcs, ra, dec, size_px=64):
    """Extract a fixed-size stamp centered on a sky coordinate using WCS."""
    x, y = wcs.world_to_pixel(SkyCoord(float(ra) * u.deg, float(dec) * u.deg))
    n = int(size_px)
    x0, y0 = int(round(float(x))) - n // 2, int(round(float(y))) - n // 2
    out = np.full((n, n), np.nan, dtype=float)
    xa, xb = max(0, x0), min(image.shape[1], x0 + n)
    ya, yb = max(0, y0), min(image.shape[0], y0 + n)
    if xa < xb and ya < yb:
        out[ya-y0:yb-y0, xa-x0:xb-x0] = image[ya:yb, xa:xb]
    return out


def _detector(row):
    import re
    match = re.search(r"D([1-6])_spx_", str(row.get("access_url", "")))
    return match.group(1) if match else "unknown"


def _local_exposure(obs_id):
    if obs_id not in _local_by_obs:
        root = Path.home() / "nasa-spherex" / "data"
        matches = sorted(root.rglob(f"*{obs_id}*.fits")) if root.exists() else []
        _local_by_obs[obs_id] = matches[0] if matches else None
    return _local_by_obs[obs_id]


def local_exposure(row):
    return _local_exposure(str(row.get("obs_id", "")))


def _cloud_location(row):
    """Read bucket and object key from the returned SIA cloud_access field."""
    info = json.loads(row["cloud_access"])
    aws = info["aws"]
    return aws["bucket_name"], aws["key"], aws.get("region", "us-east-1")


def _section_bounds(header, positions, margin_px=40, max_side=1200):
    wcs = WCS(header).celestial
    ny, nx = int(header["NAXIS2"]), int(header["NAXIS1"])
    ras = np.asarray([p[0] for p in positions], dtype=float)
    decs = np.asarray([p[1] for p in positions], dtype=float)
    x, y = wcs.world_to_pixel(SkyCoord(ras * u.deg, decs * u.deg))
    x, y = np.asarray(x), np.asarray(y)
    finite = np.isfinite(x) & np.isfinite(y)
    if not np.any(finite):
        raise ValueError("no finite section pixel coordinates for planned positions")
    x0 = max(0, int(np.floor(np.min(x[finite]))) - margin_px)
    x1 = min(nx, int(np.ceil(np.max(x[finite]))) + margin_px + 1)
    y0 = max(0, int(np.floor(np.min(y[finite]))) - margin_px)
    y1 = min(ny, int(np.ceil(np.max(y[finite]))) + margin_px + 1)
    if x1 - x0 > max_side:
        center = (x0 + x1) // 2
        x0, x1 = max(0, center - max_side // 2), min(nx, center + max_side // 2)
        if x1 - x0 < max_side:
            x0 = max(0, x1 - max_side)
    if y1 - y0 > max_side:
        center = (y0 + y1) // 2
        y0, y1 = max(0, center - max_side // 2), min(ny, center + max_side // 2)
        if y1 - y0 < max_side:
            y0 = max(0, y1 - max_side)
    return (x0, y0, x1, y1), wcs


def section_cache_path(row, bounds):
    detector = _detector(row)
    # Detector disambiguates D1..D6 files sharing one obs_id.
    identity = (str(row.get("obs_id", "")), detector, *map(int, bounds))
    name = hashlib.sha256(repr(identity).encode()).hexdigest() + ".fits"
    return RAW / "sections" / name, identity


def _save_section(path, row, source, bounds, image, flags, image_header, flag_header):
    path.parent.mkdir(parents=True, exist_ok=True)
    primary = fits.PrimaryHDU()
    primary.header["OBS_ID"] = str(row.get("obs_id", ""))
    primary.header["DETECT"] = _detector(row)
    primary.header["SOURCE"] = source
    for key, value in zip(("X0", "Y0", "X1", "Y1"), bounds):
        primary.header[key] = int(value)
    fits.HDUList([primary,
                  fits.ImageHDU(np.asarray(image), header=image_header.copy(), name="IMAGE"),
                  fits.ImageHDU(np.asarray(flags), header=flag_header.copy(), name="FLAGS")]).writeto(path, overwrite=True)


def load_cached_section(path):
    with fits.open(path, memmap=False) as hdul:
        primary = hdul[0].header
        bounds = tuple(int(primary[k]) for k in ("X0", "Y0", "X1", "Y1"))
        image_hdu, flag_hdu = hdul["IMAGE"], hdul["FLAGS"]
        return {"image": np.asarray(image_hdu.data, dtype=float), "flags": np.asarray(flag_hdu.data),
                "wcs": WCS(image_hdu.header).celestial, "x0": bounds[0], "y0": bounds[1],
                "source": str(primary.get("SOURCE", "cached")), "path": str(path), "bounds": bounds,
                "flag_header": flag_hdu.header.copy(), "image_header": image_hdu.header.copy(), "errors": []}


def _find_cached_section(row, positions):
    global _section_index_loaded
    section_dir = RAW / "sections"
    if not _section_index_loaded:
        if section_dir.exists():
            for path in section_dir.glob("*.fits"):
                try:
                    with fits.open(path, memmap=False) as hdul:
                        key = (str(hdul[0].header.get("OBS_ID", "")), str(hdul[0].header.get("DETECT", "")))
                    _section_index.setdefault(key, []).append(path)
                except Exception:
                    continue
        _section_index_loaded = True
    key = (str(row.get("obs_id", "")), _detector(row))
    for path in _section_index.get(key, []):
        try:
            with fits.open(path, memmap=False) as hdul:
                ph = hdul[0].header
                bounds = tuple(int(ph[k]) for k in ("X0", "Y0", "X1", "Y1"))
                wcs = WCS(hdul["IMAGE"].header).celestial
                ras = np.asarray([p[0] for p in positions], dtype=float)
                decs = np.asarray([p[1] for p in positions], dtype=float)
                x, y = wcs.world_to_pixel(SkyCoord(ras*u.deg, decs*u.deg))
                x, y = np.asarray(x), np.asarray(y)
                inside = ((x >= bounds[0]+32) & (x < bounds[2]-32)
                          & (y >= bounds[1]+32) & (y < bounds[3]-32))
                if inside.size and np.all(inside):
                    section = load_cached_section(path)
                    section["cache_hit"] = True
                    return section
        except Exception:
            continue
    return None


def find_cached_section(row, positions):
    return _find_cached_section(row, positions)


def _irsa_section_fallback(row, positions, size_px=1200):
    center_ra = float(np.mean([p[0] for p in positions]))
    center_dec = float(np.mean([p[1] for p in positions]))
    pixscale = float(row.get("s_pixel_scale") or 6.15)
    if not np.isfinite(pixscale) or pixscale <= 0:
        pixscale = 6.15
    size_deg = min(size_px * pixscale / 3600.0, 3.485)
    base_url = row["access_url"]
    query = urlencode({"center": f"{center_ra:.10f},{center_dec:.10f}", "size": f"{size_deg:.8f}"})
    request_url = f"{base_url}{'&' if '?' in base_url else '?'}{query}"
    last_error = None
    for attempt, delay in enumerate((0, 20, 60, 120), 1):
        if delay:
            time.sleep(delay)
        try:
            response = requests.get(request_url, timeout=180)
            if not response.ok:
                raise RuntimeError(f"HTTP {response.status_code} {response.reason}; response body: {response.text[:1000]!r}")
            with fits.open(io.BytesIO(response.content), memmap=False) as hdul:
                image_hdu, flag_hdu = hdul["IMAGE"], hdul["FLAGS"]
                image = np.asarray(image_hdu.data, dtype=float)
                flags = np.asarray(flag_hdu.data)
                wcs = WCS(image_hdu.header, fobj=hdul).celestial
                bounds = (0, 0, image.shape[1], image.shape[0])
                path, _ = section_cache_path(row, bounds)
                _save_section(path, row, "irsa", bounds, image, flags, image_hdu.header, flag_hdu.header)
                return {"image": image, "flags": flags, "wcs": wcs, "x0": 0, "y0": 0,
                        "source": "irsa", "path": str(path), "bounds": bounds,
                        "flag_header": flag_hdu.header.copy(), "image_header": image_hdu.header.copy(), "errors": []}
        except Exception as exc:
            last_error = exc
            print(f"irsa section cutout attempt {attempt}/4 failed: {exc!r}")
    raise RuntimeError(f"IRSA section cutout failed after specified 20/60/120 s backoff: {last_error!r}") from last_error


def read_section(row, positions):
    """Read one <=1200x1200 section, preferring local, anonymous S3, HTTPS, then IRSA."""
    obs_id = str(row.get("obs_id", ""))
    local_path = _local_exposure(obs_id)
    if local_path is None:
        cached = _find_cached_section(row, positions)
        if cached is not None:
            return cached
    try:
        cloud = _cloud_location(row) if local_path is None else None
    except Exception as exc:
        cloud = None
        print(f"cloud_access parse failed for {obs_id}: {exc!r}")
    attempts = []
    errors = []
    if local_path is not None:
        attempts.append(("local", str(local_path), {}))
    if cloud is not None:
        bucket, key, region = cloud
        attempts.extend([
            ("s3", f"s3://{bucket}/{key}", {"anon": True, "client_kwargs": {"region_name": region}}),
            ("https", f"https://{bucket}.s3.amazonaws.com/{key}", {"block_size": 8 * 1024 * 1024}),
        ])
    for source, url, fs_kwargs in attempts:
        try:
            open_args = {} if source == "local" else {"use_fsspec": True, "fsspec_kwargs": fs_kwargs}
            with fits.open(url, memmap=False, **open_args) as hdul:
                image_hdu, flags_hdu = hdul["IMAGE"], hdul["FLAGS"]
                bounds, wcs = _section_bounds(image_hdu.header, positions)
                path, _ = section_cache_path(row, bounds)
                if path.exists() and source != "local":
                    cached = load_cached_section(path)
                    cached["cache_hit"] = True
                    return cached
                x0, y0, x1, y1 = bounds
                image = np.asarray(image_hdu.section[y0:y1, x0:x1], dtype=float)
                flags = np.asarray(flags_hdu.section[y0:y1, x0:x1])
                image_header, flag_header = image_hdu.header.copy(), flags_hdu.header.copy()
            _save_section(path, row, source, bounds, image, flags, image_header, flag_header)
            _section_index.setdefault((obs_id, _detector(row)), []).append(path)
            return {"image": image, "flags": flags, "wcs": wcs, "x0": bounds[0], "y0": bounds[1],
                    "source": source, "path": str(path), "bounds": bounds,
                    "flag_header": flag_header, "image_header": image_header, "errors": errors}
        except Exception as exc:
            errors.append({"source": source, "error": repr(exc)})
            print(f"{source} section read failed for {obs_id}: {exc!r}")
    section = _irsa_section_fallback(row, positions)
    section["errors"] = errors
    return section
