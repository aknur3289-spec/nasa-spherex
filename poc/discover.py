"""Inspect live SPHEREx catalog schemas and one M101 D2 cutout."""

from __future__ import annotations

import csv
import io
import json
import re
import socket
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import astropy.units as u
import numpy as np
import requests
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.utils.data import conf
from astropy.wcs import WCS
from astroquery.ipac.irsa import Irsa


RA_DEG = 210.80227
DEC_DEG = 54.34895
SIZE_DEG = 0.1667
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/meta/discovery"
RAW = ROOT / "data/raw"
conf.remote_timeout = 120


def save_json(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, default=str) + "\n")


def tap_table(query: str):
    for attempt in range(3):
        try:
            return Irsa.query_tap(query).to_table()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def text_value(value: object) -> str:
    if np.ma.is_masked(value):
        return ""
    return str(value)


def probe_https(host: str) -> str | None:
    try:
        addresses = socket.getaddrinfo(host, 443, family=socket.AF_INET, type=socket.SOCK_STREAM)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(8)
        try:
            sock.connect(addresses[0][4])
        finally:
            sock.close()
        return None
    except OSError as exc:
        return f"{type(exc).__name__}: {exc}"


def schema_sample(table) -> dict:
    return {
        "columns": list(table.colnames),
        "example_row": {name: text_value(table[name][0]) for name in table.colnames}
        if len(table)
        else None,
    }


def fetch_cutout(url: str, path: Path) -> tuple[float, int, bool]:
    if path.exists():
        return 0.0, path.stat().st_size, True
    start = time.monotonic()
    for attempt in range(3):
        try:
            with requests.get(url, stream=True, timeout=(30, 120)) as response:
                response.raise_for_status()
                temp = path.with_suffix(".part")
                with temp.open("wb") as out:
                    for chunk in response.iter_content(1024 * 1024):
                        out.write(chunk)
                temp.replace(path)
            return time.monotonic() - start, path.stat().st_size, False
        except (requests.RequestException, OSError):
            path.with_suffix(".part").unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def inspect_cutout(path: Path, tap_mjd: float) -> dict:
    with fits.open(path) as hdul:
        listing = io.StringIO()
        hdul.info(output=listing)
        print(listing.getvalue())
        image = hdul["IMAGE"]
        flags = hdul["FLAGS"]
        headers = "\n\n".join(
            f"[{name}]\n{hdul[name].header.tostring(sep=chr(10), endcard=False, padding=False)}"
            for name in [0, "IMAGE", "FLAGS"]
        )
        (OUT / "header_sample.txt").write_text(headers + "\n")
        bits = []
        pixels = np.asarray(flags.data, dtype=np.uint64)
        suffixes = [int(match.group(1)) for keyword in flags.header
                    if (match := re.fullmatch(r"MSKN(\d+)", keyword))]
        suffix_is_mask = bool(suffixes) and all(n > 0 and n & (n - 1) == 0 for n in suffixes)
        for keyword in flags.header:
            match = re.fullmatch(r"MSKN(\d+)", keyword)
            if match:
                suffix = int(match.group(1))
                bit = suffix.bit_length() - 1 if suffix_is_mask else suffix
                mask = suffix if suffix_is_mask else 1 << suffix
                name = text_value(flags.header[keyword]).strip()
                desc = text_value(flags.header.get(f"MSKD{match.group(1)}", "")).strip()
                fraction = float(np.count_nonzero(pixels & mask) / pixels.size)
                bits.append({"bit": bit, "mask": mask, "name": name, "description": desc, "fraction": fraction})
        bits.sort(key=lambda item: item["bit"])
        save_json("flag_bits.json", bits)
        print("Flag bits:")
        for bit in bits:
            print(f"{bit['bit']:2} | {bit['name']:24} | {bit['description']} | {bit['fraction']:.4%}")
        spatial = WCS(image.header)
        x, y = spatial.world_to_pixel(SkyCoord(RA_DEG * u.deg, DEC_DEG * u.deg))
        spectral = WCS(image.header, fobj=hdul, key="W")
        spectral.sip = None
        wl, bw = spectral.pixel_to_world(x, y)
        wl_um = float(wl.to_value(u.um))
        print(f"Target pixel: ({x:.3f}, {y:.3f}); wavelength: {wl_um:.6f} um; bandwidth: {bw}")
        time_keywords = {key: text_value(image.header[key]) for key in image.header if key.startswith(("MJD", "DATE", "TIME"))}
        print(f"IMAGE shape: {image.data.shape}; IMAGE time keywords: {time_keywords}; TAP MJD: {tap_mjd}")
        return {"shape": list(image.data.shape), "target_pixel": [float(x), float(y)],
                "wavelength_um": wl_um, "time_keywords": time_keywords, "tap_mjd": tap_mjd,
                "bits": bits, "hdu_info": listing.getvalue(),
                "primary_version": text_value(hdul[0].header.get("VERSION", ""))}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    results: dict = {"run_utc": datetime.now(timezone.utc).isoformat()}
    irsa_error = probe_https("irsa.ipac.caltech.edu")
    if irsa_error:
        results["tap_error"] = f"IRSA HTTPS connection: {irsa_error}"
        results["sia_error"] = f"IRSA HTTPS connection: {irsa_error}"
        results["cloud_error"] = f"Public S3 HTTPS connection: {probe_https('nasa-irsa-spherex.s3.amazonaws.com') or 'reachable, but no cloud_access key available'}"
        print("IRSA unavailable:", irsa_error)
        print("Cloud fallback:", results["cloud_error"])
        save_json("results.json", results)
        return
    try:
        plane = tap_table("SELECT TOP 3 * FROM spherex.plane")
        artifact = tap_table("SELECT TOP 3 * FROM spherex.artifact")
        save_json("tap_columns.json", {"plane": schema_sample(plane), "artifact": schema_sample(artifact)})
        print("TAP schemas saved")
        query = f"""
SELECT 'https://irsa.ipac.caltech.edu/' || a.uri AS file_url, a.uri,
       p.time_bounds_lower, p.energy_bandpassname, p.planeid
FROM spherex.artifact a JOIN spherex.plane p ON a.planeid = p.planeid
WHERE 1 = CONTAINS(POINT('ICRS', {RA_DEG}, {DEC_DEG}), p.poly)
ORDER BY p.time_bounds_lower"""
        table = tap_table(query)
        with (OUT / "m101_tap.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(table.colnames)
            writer.writerows([[text_value(row[name]) for name in table.colnames] for row in table])
        bands = Counter(text_value(value) for value in table["energy_bandpassname"])
        mjds = [float(value) for value in table["time_bounds_lower"]]
        prefixes = Counter("/spherex/" + match.group(1) + "/" if (match := re.search(r"/spherex/([^/]+)/", text_value(uri))) else "unknown" for uri in table["uri"])
        results["tap"] = {"rows": len(table), "bands": dict(bands), "mjd_min": min(mjds) if mjds else None,
                          "mjd_max": max(mjds) if mjds else None, "uri_prefixes": dict(prefixes)}
        print("TAP M101:", results["tap"])
    except Exception as exc:
        results["tap_error"] = f"{type(exc).__name__}: {exc}"
        print("TAP failed:", results["tap_error"])
        table = None
    try:
        sia = Irsa.query_sia(pos=(SkyCoord(RA_DEG * u.deg, DEC_DEG * u.deg), 1 * u.arcsec),
                             collection=["spherex_dr1", "spherex_qr3"])
        results["sia"] = {"rows": len(sia), "columns": list(sia.colnames)}
        save_json("sia_columns.json", results["sia"])
        print("SIA2 M101:", results["sia"])
    except Exception as exc:
        results["sia_error"] = f"{type(exc).__name__}: {exc}"
        print("SIA2 failed:", results["sia_error"])
        sia = None
    candidate = None
    if table is not None:
        for row in table:
            if text_value(row["energy_bandpassname"]) == "SPHEREx-D2":
                candidate = (text_value(row["file_url"]), float(row["time_bounds_lower"]))
                break
    if candidate is None and sia is not None and len(sia):
        for row in sia:
            row_text = " ".join(text_value(row[name]) for name in sia.colnames)
            if "D2" in row_text:
                candidate = (text_value(row["access_url"]), float("nan"))
                break
    if candidate:
        url, mjd = candidate
        cutout_url = f"{url}?center={RA_DEG},{DEC_DEG}d&size={SIZE_DEG}"
        path = RAW / "m101_earliest_d2_cutout.fits"
        seconds, size_bytes, cached = fetch_cutout(cutout_url, path)
        results["cutout"] = {"source_url": url, "cutout_url": cutout_url, "path": str(path.relative_to(ROOT)),
                              "download_seconds": seconds, "size_bytes": size_bytes, "cached": cached}
        print("Cutout download:", results["cutout"])
        results["cutout"].update(inspect_cutout(path, mjd))
    else:
        results["cutout_error"] = "No D2 row from TAP or SIA2"
    save_json("results.json", results)


if __name__ == "__main__":
    main()
