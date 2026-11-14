"""Reproject calibrated frames and render deterministic grayscale PNGs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from astropy.wcs import WCS
from PIL import Image
from reproject import reproject_interp

if TYPE_CHECKING:
    from .frame import Frame


def field_grid(
    ra_deg: float, dec_deg: float, size_arcmin: float, pixel_arcsec: float = 6.15
) -> tuple[WCS, tuple[int, int]]:
    """Return a north-up square TAN grid with an odd pixel count per side."""
    if not (np.isfinite(ra_deg) and 0 <= ra_deg < 360):
        raise ValueError("ra_deg must be finite and in [0, 360)")
    if not (np.isfinite(dec_deg) and -90 <= dec_deg <= 90):
        raise ValueError("dec_deg must be finite and in [-90, 90]")
    if not (np.isfinite(size_arcmin) and size_arcmin > 0):
        raise ValueError("size_arcmin must be positive and finite")
    if not (np.isfinite(pixel_arcsec) and pixel_arcsec > 0):
        raise ValueError("pixel_arcsec must be positive and finite")
    pixels = max(1, int(np.ceil(size_arcmin * 60 / pixel_arcsec)))
    if pixels % 2 == 0:
        pixels += 1
    grid_wcs = WCS(naxis=2)
    grid_wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    grid_wcs.wcs.cunit = ["deg", "deg"]
    grid_wcs.wcs.crval = [ra_deg, dec_deg]
    grid_wcs.wcs.crpix = [(pixels + 1) / 2, (pixels + 1) / 2]
    grid_wcs.wcs.cdelt = [-pixel_arcsec / 3600, pixel_arcsec / 3600]
    return grid_wcs, (pixels, pixels)


def to_grid(frame: Frame, grid_wcs: WCS, shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Reproject the image and its bad-pixel mask onto a common grid."""
    image = np.asarray(frame.image, dtype=np.float32)
    bad = np.asarray(frame.bad, dtype=bool)
    if image.ndim != 2 or image.shape != bad.shape:
        raise ValueError("frame.image and frame.bad must be matching 2-D arrays")
    if not np.isfinite(image).any():
        raise ValueError("frame has no finite image pixels")
    projected, footprint = reproject_interp(
        (image, frame.wcs), grid_wcs, shape_out=shape, order="bilinear"
    )
    bad_fraction, bad_footprint = reproject_interp(
        (bad.astype(np.float32), frame.wcs), grid_wcs,
        shape_out=shape, order="bilinear"
    )
    projected_bad = (
        (bad_fraction > 0.1)
        | ~np.isfinite(bad_fraction)
        | (bad_footprint <= 0)
        | (footprint <= 0)
        | ~np.isfinite(projected)
    )
    projected = np.asarray(projected, dtype=np.float32)
    projected[projected_bad] = np.nan
    return projected, projected_bad


def stretch_params(
    images: list[np.ndarray], lo_pct: float = 5.0, hi_pct: float = 99.7
) -> dict:
    """Choose one asinh range from all frames after individual median removal."""
    if not (0 <= lo_pct < hi_pct <= 100):
        raise ValueError("percentile bounds must satisfy 0 <= lo_pct < hi_pct <= 100")
    if not images:
        raise ValueError("at least one image is required")
    centered = []
    for index, image in enumerate(images):
        values = np.asarray(image, dtype=np.float64)
        finite = values[np.isfinite(values)]
        if not finite.size:
            raise ValueError(f"image {index} has no finite pixels")
        centered.append(finite - np.median(finite))
    pooled = np.concatenate(centered)
    lo, hi = np.percentile(pooled, [lo_pct, hi_pct])
    if not lo < hi:
        raise ValueError("images have no finite contrast after median subtraction")
    return {"kind": "asinh", "lo": float(lo), "hi": float(hi), "unit": "MJy/sr"}


def _write_png(gray: np.ndarray, bad: np.ndarray, out: Path, scale: int) -> None:
    if not isinstance(scale, int) or scale < 1:
        raise ValueError("scale must be a positive integer")
    rgba = np.empty((*gray.shape, 4), dtype=np.uint8)
    rgba[..., :3] = gray[..., None]
    rgba[..., 3] = np.where(bad, 0, 255).astype(np.uint8)
    png = Image.fromarray(rgba, mode="RGBA")
    if scale != 1:
        png = png.resize((gray.shape[1] * scale, gray.shape[0] * scale), Image.Resampling.NEAREST)
    out.parent.mkdir(parents=True, exist_ok=True)
    png.save(out, format="PNG")


def to_png(
    img: np.ndarray, bad: np.ndarray, stretch: dict, out: Path, scale: int = 1
) -> dict:
    """Write an asinh grayscale PNG and return its stretch metadata."""
    values = np.asarray(img, dtype=np.float64)
    masked = np.asarray(bad, dtype=bool)
    if values.ndim != 2 or values.shape != masked.shape:
        raise ValueError("img and bad must be matching 2-D arrays")
    valid = ~masked & np.isfinite(values)
    if not valid.any():
        raise ValueError("image has no finite unmasked pixels")
    if stretch.get("kind") != "asinh" or stretch.get("unit") != "MJy/sr":
        raise ValueError("stretch must be an asinh MJy/sr mapping")
    lo, hi = float(stretch["lo"]), float(stretch["hi"])
    if not (np.isfinite(lo) and np.isfinite(hi) and lo < hi):
        raise ValueError("stretch bounds must be finite and increasing")
    median = float(np.median(values[valid]))
    centered = values - median
    clipped = np.clip((centered - lo) / (hi - lo), 0, 1)
    mapped = np.arcsinh(10 * clipped) / np.arcsinh(10)
    gray = np.rint(np.nan_to_num(mapped, nan=0) * 255).astype(np.uint8)
    _write_png(gray, ~valid, out, scale)
    return {"kind": "asinh", "lo": lo, "hi": hi, "unit": "MJy/sr",
            "median_subtracted_mjysr": median}


def diff_png(
    a: np.ndarray, b: np.ndarray, bad: np.ndarray, out: Path, noise: float
) -> dict:
    """Write a symmetric ±5σ difference PNG from (a - scale*b)/noise."""
    first = np.asarray(a, dtype=np.float64)
    second = np.asarray(b, dtype=np.float64)
    masked = np.asarray(bad, dtype=bool)
    if first.ndim != 2 or first.shape != second.shape or first.shape != masked.shape:
        raise ValueError("a, b, and bad must be matching 2-D arrays")
    if not (np.isfinite(noise) and noise > 0):
        raise ValueError("noise must be positive and finite")
    valid = ~masked & np.isfinite(first) & np.isfinite(second)
    if not valid.any():
        raise ValueError("difference has no finite unmasked pixels")
    bright = valid & (first > np.percentile(first[valid], 90)) & (
        second > np.percentile(second[valid], 90)) & (second > 0)
    ratios = first[bright] / second[bright]
    ratios = ratios[np.isfinite(ratios) & (ratios > 0)]
    scale = float(np.median(ratios)) if ratios.size else 1.0
    sigma = (first - scale * second) / noise
    gray = np.rint((np.clip(np.nan_to_num(sigma, nan=0), -5, 5) + 5) * 25.5).astype(np.uint8)
    _write_png(gray, ~valid, out, 1)
    return {"kind": "difference", "lo": -5.0, "hi": 5.0, "unit": "sigma", "scale_b": scale}
