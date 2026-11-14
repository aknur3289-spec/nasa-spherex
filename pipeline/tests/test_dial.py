"""Offline dial packaging checks."""
from pathlib import Path

import numpy as np
from astropy.wcs import WCS

from pipeline.build_dial import _inside, _reference, _science_scorer


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
