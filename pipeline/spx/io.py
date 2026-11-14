"""Search IRSA for SPHEREx frames and cache validated image cutouts."""

from __future__ import annotations

import csv
import hashlib
import logging
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http.client import IncompleteRead, RemoteDisconnected
from pathlib import Path
from urllib.parse import urlsplit

import astropy.units as u
import numpy as np
import requests
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.utils.data import conf
from astropy.wcs import WCS
from astroquery.ipac.irsa import Irsa

LOG = logging.getLogger(__name__)
conf.remote_timeout = 120
INDEX_COLUMNS = (
    "field_id", "file_url", "source_url", "collection", "mjd", "detector",
    "bandpassname", "planeid", "obs_id", "local_path", "bytes", "status",
    "error", "downloaded_utc", "sha256",
)
RETRY_DELAYS = (5, 15, 30)


def _text(value: object) -> str:
    return "" if np.ma.is_masked(value) or value is None else str(value)


def _collection(uri: str) -> str:
    match = re.search(r"/spherex/(dr1|qr3)/", "/" + uri.lstrip("/"), re.I)
    return f"spherex_{match.group(1).lower()}" if match else ""


def _version(row: dict) -> tuple[int, ...]:
    source = f"{row.get('file_url', '')} {row.get('provenance_version', '')}"
    match = re.search(r"l2b(?:_retry)?-v(\d+)-(\d+)-(\d+)", source, re.I)
    if match:
        return tuple(map(int, match.groups()))
    match = re.search(r"(?:^|\s)(\d+(?:\.\d+)+)(?:\s|$)", source)
    return tuple(map(int, match.group(1).split("."))) if match else ()


def _prefer(row: dict) -> tuple[tuple[int, ...], int]:
    return _version(row), int(row.get("collection") == "spherex_dr1")


def _deduplicate(rows: list[dict]) -> list[dict]:
    kept: list[dict] = []
    keys: dict[tuple[str, str], int] = {}
    for row in rows:
        basename = Path(urlsplit(row["file_url"]).path).name
        identities = [("basename", basename)]
        if row.get("obs_id") and row.get("detector"):
            identities.append(("obs_detector", f"{row['obs_id']}:{row['detector']}"))
        hits = {keys[key] for key in identities if key in keys}
        if not hits:
            index = len(kept)
            kept.append(row)
            for key in identities:
                keys[key] = index
            continue
        index = min(hits)
        old = kept[index]
        if _prefer(row) > _prefer(old):
            LOG.info("Dropped duplicate %s; kept %s", old["file_url"], row["file_url"])
            kept[index] = row
        else:
            LOG.info("Dropped duplicate %s; kept %s", row["file_url"], old["file_url"])
        for key in identities:
            keys[key] = index
    return sorted(kept, key=lambda item: float(item["mjd"]))


def search_frames(
    ra_deg: float, dec_deg: float, detectors: list[int] | None = None,
    collections: tuple[str, ...] = ("spherex_dr1", "spherex_qr3"),
    mjd_range: tuple[float, float] | None = None, method: str = "tap",
) -> list[dict]:
    """Return one catalog row per exposure covering a sky position."""
    if method not in {"tap", "sia"}:
        raise ValueError("method must be tap or sia")
    selected = sorted(set(detectors or range(1, 7)))
    if not selected or any(detector not in range(1, 7) for detector in selected):
        raise ValueError("detectors must be in 1..6")
    if not collections or any(name not in {"spherex_dr1", "spherex_qr3"} for name in collections):
        raise ValueError("unsupported collection")
    if method == "tap":
        bands = ", ".join(f"'SPHEREx-D{number}'" for number in selected)
        collection_clause = " OR ".join(
            f"a.uri LIKE '%/spherex/{name.removeprefix('spherex_')}/%'"
            for name in collections
        )
        time_clause = ""
        if mjd_range is not None:
            time_clause = f" AND p.time_bounds_lower BETWEEN {float(mjd_range[0])} AND {float(mjd_range[1])}"
        query = (
            "SELECT 'https://irsa.ipac.caltech.edu/' || a.uri AS file_url, "
            "a.uri, p.time_bounds_lower, p.energy_bandpassname, p.planeid, "
            "p.obsid, p.provenance_version "
            "FROM spherex.artifact a JOIN spherex.plane p ON a.planeid = p.planeid "
            f"WHERE 1 = CONTAINS(POINT('ICRS', {float(ra_deg)}, {float(dec_deg)}), p.poly) "
            f"AND p.energy_bandpassname IN ({bands}) AND ({collection_clause})"
            f"{time_clause} ORDER BY p.time_bounds_lower"
        )
        table = Irsa.query_tap(query).to_table()
        rows = []
        for item in table:
            uri = _text(item["uri"])
            band = _text(item["energy_bandpassname"])
            rows.append({
                "file_url": _text(item["file_url"]), "uri": uri,
                "collection": _collection(uri), "mjd": float(item["time_bounds_lower"]),
                "detector": int(band.rsplit("D", 1)[1]), "bandpassname": band,
                "planeid": _text(item["planeid"]), "obs_id": _text(item["obsid"]),
                "provenance_version": _text(item["provenance_version"]),
            })
    else:
        position = SkyCoord(ra_deg * u.deg, dec_deg * u.deg)
        table = Irsa.query_sia(pos=(position, 1 * u.arcsec), collection=list(collections))
        rows = []
        for item in table:
            band = _text(item["energy_bandpassname"])
            if band not in {f"SPHEREx-D{number}" for number in selected}:
                continue
            mjd = float(item["t_min"])
            if mjd_range is not None and not mjd_range[0] <= mjd <= mjd_range[1]:
                continue
            url = _text(item["access_url"])
            uri = urlsplit(url).path.lstrip("/")
            rows.append({
                "file_url": url, "uri": uri,
                "collection": _text(item["obs_collection"]) or _collection(uri),
                "mjd": mjd, "detector": int(band.rsplit("D", 1)[1]),
                "bandpassname": band, "planeid": "", "obs_id": _text(item["obs_id"]),
            })
    return _deduplicate([row for row in rows if row["collection"] in collections])


def cutout_url(file_url: str, ra_deg: float, dec_deg: float, size_deg: float) -> str:
    """Build an IRSA square cutout URL in degrees."""
    return f"{file_url}?center={ra_deg},{dec_deg}d&size={size_deg}"


def _local_path(row: dict, ra_deg: float, dec_deg: float, size_deg: float, outdir: Path) -> Path:
    basename = Path(urlsplit(row["file_url"]).path).name.removesuffix(".fits")
    return outdir / f"{basename}__c{ra_deg:.5f}_{dec_deg:+.5f}_s{size_deg:.4f}.fits"


def _valid_fits(path: Path) -> bool:
    try:
        with fits.open(path) as hdul:
            hdul.verify("exception")
            return "IMAGE" in hdul and "WCS-WAVE" in hdul
    except (OSError, ValueError, KeyError):
        return False


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, requests.HTTPError):
        return exc.response is not None and 500 <= exc.response.status_code < 600
    return isinstance(exc, (TimeoutError, IncompleteRead, RemoteDisconnected,
                            ConnectionError, requests.Timeout, requests.ConnectionError))


def fetch_cutout(
    row: dict, ra_deg: float, dec_deg: float, size_deg: float,
    outdir: Path = Path("data/raw"),
) -> Path | None:
    """Download and slim one cutout, or return an existing valid FITS file."""
    path = _local_path(row, ra_deg, dec_deg, size_deg, Path(outdir))
    if path.exists() and _valid_fits(path):
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    source = cutout_url(row["file_url"], ra_deg, dec_deg, size_deg)
    part = path.with_name(path.name + ".part")
    slim = path.with_name(path.name + ".slim.part")
    for attempt in range(3):
        try:
            with requests.get(source, stream=True, timeout=(30, 120)) as response:
                response.raise_for_status()
                with part.open("wb") as output:
                    for chunk in response.iter_content(1024 * 1024):
                        output.write(chunk)
            with fits.open(part) as hdul:
                hdul.verify("exception")
                if "IMAGE" not in hdul or "WCS-WAVE" not in hdul:
                    raise ValueError("cutout missing IMAGE or WCS-WAVE")
                fits.HDUList([hdu.copy() for hdu in hdul if hdu.name.upper() not in {"EPSF", "PSF"}]).writeto(slim, overwrite=True)
            slim.replace(path)
            return path
        except Exception as exc:
            if not _retryable(exc) or attempt == 2:
                raise
            LOG.warning("Cutout retry %s/3 for %s: %s", attempt + 1, source, exc)
            time.sleep(RETRY_DELAYS[attempt])
        finally:
            part.unlink(missing_ok=True)
            slim.unlink(missing_ok=True)
    return None


def _validate(path: Path, ra_deg: float, dec_deg: float, size_deg: float) -> str:
    with fits.open(path) as hdul:
        image = hdul["IMAGE"]
        shape = image.data.shape
        expected = (size_deg * 3600 / 6.15) ** 2
        if len(shape) != 2 or shape[0] * shape[1] < 0.8 * expected:
            return "partial"
        x, y = WCS(image.header).world_to_pixel(SkyCoord(ra_deg * u.deg, dec_deg * u.deg))
        if not (np.isfinite(x) and np.isfinite(y) and 0 <= x < shape[1] and 0 <= y < shape[0]):
            return "outside"
    return "ok"


def _spread(rows: list[dict], limit: int | None) -> list[dict]:
    if limit is None or limit >= len(rows):
        return rows
    if limit < 1:
        raise ValueError("limit must be positive")
    ordered = sorted(rows, key=lambda row: float(row["mjd"]))
    if limit == 1:
        return [ordered[len(ordered) // 2]]
    positions = [round(i * (len(ordered) - 1) / (limit - 1)) for i in range(limit)]
    return [ordered[position] for position in positions]


def _fetch_one(row: dict, field_id: str, ra_deg: float, dec_deg: float, size_deg: float) -> dict:
    path = _local_path(row, ra_deg, dec_deg, size_deg, Path("data/raw") / field_id)
    cached = path.exists() and _valid_fits(path)
    result = {key: row.get(key, "") for key in INDEX_COLUMNS}
    result.update(field_id=field_id, source_url=cutout_url(row["file_url"], ra_deg, dec_deg, size_deg),
                  local_path=str(path), bytes=0, status="error", error="", downloaded_utc="", sha256="")
    result["_was_cached"] = cached
    try:
        actual = fetch_cutout(row, ra_deg, dec_deg, size_deg, outdir=path.parent)
        if actual is None:
            raise RuntimeError("download returned no path")
        validation = _validate(actual, ra_deg, dec_deg, size_deg)
        result["status"] = validation if validation != "ok" else ("cached" if cached else "ok")
        result["bytes"] = actual.stat().st_size
        digest = hashlib.sha256()
        with actual.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        result["sha256"] = digest.hexdigest()
        result["downloaded_utc"] = datetime.fromtimestamp(actual.stat().st_mtime, timezone.utc).isoformat()
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        LOG.error("Failed %s: %s", row["file_url"], result["error"])
    return result


def fetch_field(
    field_id: str, ra_deg: float, dec_deg: float, size_deg: float,
    detectors: list[int] | None, max_workers: int = 6, limit: int | None = None,
    *, method: str = "tap",
) -> Path:
    """Fetch a field and write its raw catalog and download index."""
    if not 1 <= max_workers <= 8:
        raise ValueError("max_workers must be between 1 and 8")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", field_id):
        raise ValueError("field_id must contain only letters, digits, underscore or hyphen")
    started = time.monotonic()
    rows = search_frames(ra_deg, dec_deg, detectors=detectors, method=method)
    print(f"Found {len(rows)} rows; detectors={dict(sorted(Counter(row['detector'] for row in rows).items()))}; collections={dict(sorted(Counter(row['collection'] for row in rows).items()))}")
    if rows:
        print(f"MJD span: {min(row['mjd'] for row in rows):.6f}–{max(row['mjd'] for row in rows):.6f}")
    chosen = _spread(rows, limit)
    index = Path("data/meta") / field_id / "raw_index.csv"
    index.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_fetch_one, row, field_id, ra_deg, dec_deg, size_deg) for row in chosen]
        for future in as_completed(futures):
            results.append(future.result())
            done = len(results)
            if done % 10 == 0 or done == len(futures):
                elapsed = time.monotonic() - started
                mb = sum(int(item["bytes"]) for item in results) / 1_000_000
                eta = elapsed / done * (len(futures) - done) if done else 0
                print(f"Progress {done}/{len(futures)}; {mb:.2f} MB; ETA {eta:.0f} s", flush=True)
    order = {row["file_url"]: n for n, row in enumerate(chosen)}
    results.sort(key=lambda row: order[row["file_url"]])
    with index.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=INDEX_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    counts = Counter(item["status"] for item in results)
    cached_count = sum(item["_was_cached"] and item["status"] != "error" for item in results)
    downloaded_count = sum(not item["_was_cached"] and item["status"] != "error" for item in results)
    mb = sum(int(item["bytes"]) for item in results) / 1_000_000
    print(f"downloaded={downloaded_count} cached={cached_count} failed={counts['error']} total_mb={mb:.2f} wall_s={time.monotonic() - started:.1f}")
    return index
