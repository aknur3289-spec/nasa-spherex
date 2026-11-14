"""Offline dial packaging checks."""
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

import pipeline.build_dial as dial
from pipeline.build_dial import _inside, _neptune_centroid, _peak, _reference, _science_scorer


def test_reference_prefers_lowest_bad_fraction(tmp_path: Path) -> None:
    first = tmp_path / "a.fits"
    second = tmp_path / "b.fits"
    first.touch()
    second.touch()
    rows = [
        {"window_id": "2", "status": "ok", "local_path": str(first),
         "bad_frac": "0.1", "mjd": "61018", "obs_id": "a"},
        {"window_id": "2", "status": "ok", "local_path": str(second),
         "bad_frac": "0.0", "mjd": "61019", "obs_id": "b"},
    ]
    assert _reference(rows, 2)["obs_id"] == "b"


def test_coverage_requires_search_margin() -> None:
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [12, 4]
    wcs.wcs.crpix = [50, 50]
    wcs.wcs.cdelt = [-0.001, 0.001]
    candidate = {"wcs": wcs, "shape": (100, 100)}
    assert _inside(candidate, 12, 4)
    edge_ra, edge_dec = wcs.pixel_to_world_values(5, 50)
    assert not _inside(candidate, edge_ra, edge_dec)


def test_science_scorer_finds_peak_near_crosshair() -> None:
    image = np.zeros((64, 64), dtype=float)
    image[32, 33] = 20
    snr, offset = _science_scorer()(image, np.ones_like(image),
                                    np.zeros_like(image), 0.0)
    assert np.isfinite(snr) and snr > 0
    assert offset <= 20


def test_dial_pixel_peak_uses_central_radius_and_bad_mask() -> None:
    image = np.indices((101, 101))[0].astype(float) % 3
    image[50, 51] = 10
    image[50, 80] = 50
    image[50, 49] = 100
    bad = np.zeros_like(image, dtype=bool)
    bad[50, 49] = True
    result = _peak(image, bad)
    assert result is not None
    assert result[0] > 0
    assert result[1] == 1


def test_neptune_centroid_requires_bright_nearby_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dial, "ROOT", tmp_path)
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [359.6, -1.6]
    wcs.wcs.crpix = [51, 51]
    wcs.wcs.cdelt = [-6.15 / 3600, 6.15 / 3600]
    yy, xx = np.indices((101, 101))
    background = 0.01 * ((xx + yy) % 3)
    source = 80 * np.exp(-((xx - 50.3) ** 2 + (yy - 50.2) ** 2) / 2)
    def save(image: np.ndarray) -> None:
        fits.HDUList([fits.PrimaryHDU(),
                      fits.ImageHDU(image.astype(np.float32), header=wcs.to_header(), name="IMAGE"),
                      fits.ImageHDU(np.zeros_like(image, dtype=np.float32), name="ZODI"),
                      fits.ImageHDU(np.zeros_like(image, dtype=np.int32), name="FLAGS")]).writeto(
                          tmp_path / "target.fits", overwrite=True)
    save(background + source)
    result = _neptune_centroid([{"path": "target.fits", "distance_au": 29.9}], 359.6, -1.6)
    assert result["horizons_offset_px"] < 1
    assert result["peak_mjysr"] > 50
    save(background + 0.1 * source)
    with pytest.raises(ValueError, match="sanity failed"):
        _neptune_centroid([{"path": "target.fits", "distance_au": 29.9}], 359.6, -1.6)


