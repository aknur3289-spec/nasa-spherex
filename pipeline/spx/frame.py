"""Offline SPHEREx cutout reading and epoch metadata."""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from astropy import units as u
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS

LOG = logging.getLogger(__name__)

BAD_BITS: tuple[str, ...] = (
    "TRANSIENT", "OVERFLOW", "SUR_ERROR", "NONFUNC", "DICHROIC",
    "MISSING_DATA", "HOT", "COLD", "PHANMISS", "NONLINEAR", "PERSIST",
    "OUTLIER", "CROSSTALK", "GHOST", "GHOST_FPA", "GHOST_EXT",
    "STREAK", "BLOOM", "SNOWBALL", "HALO",
)

BANDS_UM = {
    1: (0.75, 1.09), 2: (1.10, 1.62), 3: (1.63, 2.41),
    4: (2.42, 3.82), 5: (3.83, 4.41), 6: (4.42, 5.00),
}

EPOCH_COLUMNS = (
    "frame_id", "field_id", "obs_id", "detector", "collection",
    "processing_version", "mjd", "obs_time_utc", "wavelength_um",
    "bandwidth_um", "x_pix", "y_pix", "bad_pixel_fraction", "target_bad",
    "zodi_median_mjysr", "image_median_mjysr", "noise_mad_mjysr",
    "psf_fwhm_arcsec", "survey_pass", "source_url", "local_path",
    "downloaded_utc", "status",
)

_WARNED_BITS: set[str] = set()


@dataclass
class Frame:
    image: np.ndarray
    bad: np.ndarray
    variance: np.ndarray
    wcs: WCS
    meta: dict


def bad_mask(flags: np.ndarray, flags_header: fits.Header) -> np.ndarray:
    """Mask only bad flag names defined in the FITS header."""
    bits = {
        str(value).strip().upper(): int(key[4:])
        for key, value in flags_header.items()
        if key.startswith("MSKN") and key[4:].isdigit()
    }
    mask_value = 0
    for name in BAD_BITS:
        if name in bits:
            mask_value |= 1 << bits[name]
        elif name not in _WARNED_BITS:
            LOG.warning("FLAGS header has no %s bit", name)
            _WARNED_BITS.add(name)
    return (np.asarray(flags, dtype=np.uint64) & mask_value) != 0


def wavelength_at(hdul: fits.HDUList, ra_deg: float, dec_deg: float) -> tuple[float, float, float, float]:
    """Return target wavelength, bandwidth in um, and zero-based pixel position."""
    header = hdul["IMAGE"].header
    x_pix, y_pix = WCS(header).world_to_pixel_values(ra_deg, dec_deg)
    spectral_wcs = WCS(header, fobj=hdul, key="W")
    spectral_wcs.sip = None
    wavelength, bandwidth = spectral_wcs.pixel_to_world(x_pix, y_pix)
    return (
        float(wavelength.to_value(u.um)),
        float(bandwidth.to_value(u.um)),
        float(x_pix), float(y_pix),
    )


def _median(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    return float(np.median(finite)) if finite.size else float("nan")


def _target_bad(bad: np.ndarray, x_pix: float, y_pix: float) -> bool:
    if not np.isfinite(x_pix) or not np.isfinite(y_pix):
        return True
    x, y = round(x_pix), round(y_pix)
    if x < 0 or y < 0 or x >= bad.shape[1] or y >= bad.shape[0]:
        return True
    return bool(bad[max(0, y - 1):y + 2, max(0, x - 1):x + 2].any())


def read_frame(path: Path, ra_deg: float, dec_deg: float) -> Frame:
    """Read one local MEF and calculate cleaned image and epoch metrics."""
    with fits.open(path, memmap=False) as hdul:
        header = hdul["IMAGE"].header
        image = np.asarray(hdul["IMAGE"].data, dtype=np.float32).copy()
        zodi = np.asarray(hdul["ZODI"].data, dtype=np.float32)
        variance = np.asarray(hdul["VARIANCE"].data, dtype=np.float32).copy()
        flags = hdul["FLAGS"].data
        if image.ndim != 2 or any(array.shape != image.shape for array in (zodi, variance, flags)):
            raise ValueError("IMAGE, ZODI, VARIANCE and FLAGS must have matching 2D shapes")
        bad = bad_mask(flags, hdul["FLAGS"].header)
        image -= zodi
        image[bad] = np.nan
        wavelength_um, bandwidth_um, x_pix, y_pix = wavelength_at(hdul, ra_deg, dec_deg)
        detector = int(header["DETECTOR"])
        lower_um, upper_um = BANDS_UM[detector]
        bad_fraction = float(bad.mean())
        status = "ok"
        if not np.isfinite(wavelength_um) or not lower_um <= wavelength_um <= upper_um:
            status = "bad_wavelength"
        elif bad_fraction > 0.30:
            status = "too_many_bad"
        mjd = float(header["MJD-OBS"])
        obs_time_utc = Time(mjd, format="mjd", scale="utc").isot + "Z"
        median = _median(image)
        meta = {
            "obs_id": str(header["OBSID"]).strip(),
            "detector": detector,
            "processing_version": str(hdul[0].header["VERSION"]).strip(),
            "mjd": mjd,
            "obs_time_utc": obs_time_utc,
            "wavelength_um": wavelength_um,
            "bandwidth_um": bandwidth_um,
            "x_pix": x_pix,
            "y_pix": y_pix,
            "bad_pixel_fraction": bad_fraction,
            "target_bad": _target_bad(bad, x_pix, y_pix),
            "zodi_median_mjysr": _median(zodi),
            "image_median_mjysr": median,
            "noise_mad_mjysr": float(1.4826 * _median(np.abs(image - median))),
            "psf_fwhm_arcsec": header.get("PSF_FWHM", ""),
            "survey_pass": "",
            "status": status,
        }
        return Frame(image=image, bad=bad, variance=variance, wcs=WCS(header), meta=meta)


def build_epochs(field_id: str, ra_deg: float, dec_deg: float) -> Path:
    """Read local raw_index.csv and write sorted epochs.csv for a field."""
    index_path = Path("data/meta") / field_id / "raw_index.csv"
    output_path = index_path.with_name("epochs.csv")
    with index_path.open(newline="") as source:
        raw_rows = list(csv.DictReader(source))
    rows = []
    for raw in raw_rows:
        if raw.get("status") not in ("ok", "cached"):
            continue
        path = Path(raw.get("local_path", ""))
        row = {key: "" for key in EPOCH_COLUMNS}
        row.update({key: raw.get(key, "") for key in (
            "field_id", "collection", "source_url", "local_path", "downloaded_utc",
        )})
        row["field_id"] = field_id
        try:
            frame = read_frame(path, ra_deg, dec_deg)
            row.update(frame.meta)
            if not all(row.get(key) for key in (
                "source_url", "obs_id", "mjd", "obs_time_utc", "detector",
                "wavelength_um", "processing_version", "collection", "downloaded_utc",
            )):
                row["status"] = "error"
                LOG.error("Incomplete provenance for %s", path)
        except Exception:
            LOG.exception("Could not read %s", path)
            row["status"] = "error"
            row["obs_id"] = raw.get("obs_id", "")
            row["detector"] = raw.get("detector", "")
            row["mjd"] = raw.get("mjd", "")
        rows.append(row)
    rows.sort(key=lambda row: (
        float(row["mjd"]) if row["mjd"] else float("inf"),
        str(row["detector"]), str(row["obs_id"]), str(row["local_path"]),
    ))
    for number, row in enumerate(rows, 1):
        row["frame_id"] = f"f{number:03d}"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=EPOCH_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return output_path
