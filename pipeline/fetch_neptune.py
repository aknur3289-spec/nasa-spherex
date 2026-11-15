"""Build Neptune science cutouts and fixed-sky June 2026 templates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
from astropy import units as u
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.spx import io

META = Path("data/meta/neptune")
RAW = Path("data/raw/neptune")
ZIP_PATH = Path("data/meta/neptune_cutouts.zip")
SIZE_DEG = 10 / 60
BAD_BITS = 333057605
SAT_BITS = 67141634
EPOCH_COLUMNS = (
    "obs_id", "detector", "mjd", "wavelength_um", "window_id", "access_url",
    "cloud_key", "local_path", "bad_frac", "sat_frac", "eph_ra", "eph_dec",
    "delta_au", "status", "error",
)
TEMPLATE_COLUMNS = (
    "science_obs_id", "template_obs_id", "detector", "delta_lambda_um",
    "science_wavelength_um", "template_wavelength_um", "template_local_path",
    "science_eph_ra", "science_eph_dec",
)


def window_id(mjd: float) -> int:
    """Assign the three observed seasonal windows, including adjacent July days."""
    month = Time(mjd, format="mjd", scale="utc").to_datetime().strftime("%Y-%m")
    windows = {"2025-06": 1, "2025-07": 1, "2025-12": 2,
               "2026-06": 3, "2026-07": 3}
    if month not in windows:
        raise ValueError(f"MJD {mjd} is outside the three Neptune windows")
    return windows[month]


def central_fractions(flags: np.ndarray) -> tuple[float, float]:
    """Measure the stated BAD and SAT masks in the central 5 by 5 pixels."""
    if flags.ndim != 2 or min(flags.shape) < 5:
        raise ValueError("FLAGS needs at least a 5 by 5 image")
    y0 = (flags.shape[0] - 5) // 2
    x0 = (flags.shape[1] - 5) // 2
    central = np.asarray(flags[y0:y0 + 5, x0:x0 + 5], dtype=np.uint64)
    return float(np.count_nonzero(central & BAD_BITS) / 25), float(np.count_nonzero(central & SAT_BITS) / 25)


def inspect_cutout(path: Path) -> dict:
    """Read FITS identity, centre wavelength, and central FLAGS fractions."""
    with fits.open(path, memmap=False) as hdul:
        image = hdul["IMAGE"]
        height, width = image.data.shape
        spectral = WCS(image.header, fobj=hdul, key="W")
        spectral.sip = None
        wavelength, _ = spectral.pixel_to_world((width - 1) / 2, (height - 1) / 2)
        bad_frac, sat_frac = central_fractions(hdul["FLAGS"].data)
        return {"obs_id": str(image.header["OBSID"]).strip(),
                "detector": int(image.header["DETECTOR"]),
                "mjd": float(image.header["MJD-OBS"]),
                "wavelength_um": float(wavelength.to_value(u.um)),
                "bad_frac": bad_frac, "sat_frac": sat_frac}


def _catalog_at(ra_deg: float, dec_deg: float) -> list[dict]:
    cache = META / "sia" / (hashlib.sha256(f"{ra_deg:.6f},{dec_deg:.6f}".encode()).hexdigest()[:20] + ".json")
    if cache.is_file():
        return json.loads(cache.read_text())
    rows = io.search_sia_point(ra_deg, dec_deg)
    cache.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache.with_suffix(".part")
    temporary.write_text(json.dumps(rows) + "\n")
    temporary.replace(cache)
    return rows


def _same_file(a: str, b: str) -> bool:
    return Path(urlsplit(a).path).name == Path(urlsplit(b).path).name


def _source_row(raw: dict, sia: list[dict]) -> dict:
    matching = next((item for item in sia if _same_file(item["file_url"], raw["file_url"])), None)
    return {**raw, **({"access_url": matching.get("access_url", ""),
                      "cloud_key": matching.get("cloud_key", ""),
                      "cloud_bucket": matching.get("cloud_bucket", "")}
                     if matching else {})}


def select_templates(sia: list[dict], detector: int) -> list[dict]:
    """Choose up to three distinct June 2026 exposures, same detector first."""
    candidates = []
    for row in sia:
        try:
            if window_id(float(row["mjd"])) == 3:
                candidates.append(row)
        except ValueError:
            continue
    candidates.sort(key=lambda row: (int(row["detector"]) != detector,
                                     abs(float(row["mjd"]) - 61215), row["file_url"]))
    selected = []
    seen = set()
    for row in candidates:
        basename = Path(urlsplit(row["file_url"]).path).name
        if basename not in seen:
            selected.append(row)
            seen.add(basename)
        if len(selected) == 3:
            break
    return selected


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".part")
    with temporary.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _write_outputs(epochs: list[dict], templates: list[dict]) -> None:
    _write_csv(META / "epochs.csv", EPOCH_COLUMNS, epochs)
    _write_csv(META / "templates.csv", TEMPLATE_COLUMNS, templates)
    passes = []
    for number in (1, 2, 3):
        group = [row for row in epochs if row["window_id"] == number]
        good = [row for row in group if row["status"] == "ok"]
        passes.append({"window_id": number, "catalog_exposures": len(group),
                       "cutouts_ready": len(good),
                       "detectors_ready": dict(sorted(Counter(str(row["detector"]) for row in good).items())),
                       "mjd_min": min((row["mjd"] for row in group), default=None),
                       "mjd_max": max((row["mjd"] for row in group), default=None)})
    (META / "passes.json").write_text(json.dumps({"passes": passes}, indent=2) + "\n")
    errors = [row for row in epochs if row["status"] != "ok"]
    text = ["# Neptune data handoff", "",
            "Ephemerides in `raw_index.csv` are Horizons geocentric truth at each exposure MJD.",
            "Window 1 is June–early July 2025; window 2 is December 2025; window 3 is June–early July 2026.",
            "Wavelength is from WCS-WAVE at the cutout centre. BAD and SAT fractions use the central 5×5 FLAGS pixels.",
            "Templates are centred on each December science exposure's Neptune sky position, using June 2026 frames.", "",
            "| Window | Catalog | Ready |", "| --- | ---: | ---: |"]
    text.extend(f"| {p['window_id']} | {p['catalog_exposures']} | {p['cutouts_ready']} |" for p in passes)
    text.extend(["", f"Template links: {len(templates)}. Failed/pending science cutouts: {len(errors)}.",
                 "Paths: `epochs.csv`, `passes.json`, `templates.csv`, `templates/`, and `../neptune_cutouts.zip`.",
                 "FITS cutouts and ZIP stay outside Git; only the CSV, JSON, and this handoff are committed."])
    if errors:
        text.append("Incomplete inputs are listed with status and error in `epochs.csv`.")
    (META / "HANDOFF.md").write_text("\n".join(text) + "\n")


def _write_zip(epochs: list[dict], templates: list[dict]) -> None:
    paths = {Path(row["local_path"]) for row in epochs if row["status"] == "ok"}
    paths.update(Path(row["template_local_path"]) for row in templates)
    temporary = ZIP_PATH.with_suffix(".part")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            if path.is_file():
                archive.write(path, arcname=str(path))
    temporary.replace(ZIP_PATH)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-templates", action="store_true", help="finish science cutouts first")
    args = parser.parse_args()
    with (META / "raw_index.csv").open(newline="") as source:
        raw_rows = list(csv.DictReader(source))
    epochs, templates = [], []
    for index, raw in enumerate(raw_rows, 1):
        ra_deg, dec_deg = float(raw["eph_ra_deg"]), float(raw["eph_dec_deg"])
        row = {"obs_id": raw["obs_id"], "detector": int(raw["detector"]),
               "mjd": float(raw["mjd"]), "wavelength_um": "",
               "window_id": window_id(float(raw["mjd"])), "access_url": raw["file_url"],
               "cloud_key": "", "local_path": "", "bad_frac": "", "sat_frac": "",
               "eph_ra": ra_deg, "eph_dec": dec_deg, "delta_au": float(raw["delta_au"]),
               "status": "pending", "error": ""}
        try:
            sia = _catalog_at(ra_deg, dec_deg)
            source_row = _source_row(raw, sia)
            row["access_url"] = source_row.get("access_url") or raw["file_url"]
            row["cloud_key"] = source_row.get("cloud_key", "")
            path = io.fetch_cutout(source_row, ra_deg, dec_deg, SIZE_DEG, RAW)
            if path is None:
                raise RuntimeError("cutout fetch returned no path")
            row.update(inspect_cutout(path))
            row["local_path"] = str(path)
            row["status"] = "ok"
            if row["window_id"] == 2 and not args.no_templates:
                for candidate in select_templates(sia, int(row["detector"])):
                    try:
                        template_path = io.fetch_cutout(candidate, ra_deg, dec_deg, SIZE_DEG,
                                                        META / "templates")
                        if template_path is None:
                            continue
                        measured = inspect_cutout(template_path)
                        templates.append({"science_obs_id": row["obs_id"],
                                          "template_obs_id": measured["obs_id"],
                                          "detector": measured["detector"],
                                          "delta_lambda_um": abs(row["wavelength_um"] - measured["wavelength_um"]),
                                          "science_wavelength_um": row["wavelength_um"],
                                          "template_wavelength_um": measured["wavelength_um"],
                                          "template_local_path": str(template_path),
                                          "science_eph_ra": ra_deg, "science_eph_dec": dec_deg})
                    except Exception as exc:
                        print(f"Template failed for {row['obs_id']}: {type(exc).__name__}: {exc}", flush=True)
        except Exception as exc:
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
        epochs.append(row)
        _write_outputs(epochs, templates)
        print(f"Neptune {index}/{len(raw_rows)}: {row['status']} templates={len(templates)}", flush=True)
    _write_zip(epochs, templates)
    print(f"Ready: {sum(row['status'] == 'ok' for row in epochs)}/{len(epochs)} science cutouts; "
          f"{len(templates)} template links; {ZIP_PATH}")
    linked = Counter(row["science_obs_id"] for row in templates)
    incomplete = any(row["status"] != "ok" for row in epochs)
    if not args.no_templates:
        incomplete |= any(linked[row["obs_id"]] < 2 for row in epochs
                          if row["window_id"] == 2 and row["status"] == "ok")
    if incomplete:
        raise SystemExit("Neptune package is incomplete; inspect epochs.csv and templates.csv")


if __name__ == "__main__":
    main()
