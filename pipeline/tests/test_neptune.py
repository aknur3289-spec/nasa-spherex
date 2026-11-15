"""Offline checks for Neptune metadata and cloud section packaging."""

from pathlib import Path

import numpy as np
import pytest
import requests
from astropy.io import fits
from astropy.wcs import WCS

from pipeline.fetch_neptune import central_fractions, select_templates, window_id
from pipeline.spx import io
from pipeline.spx.io import _cloud_location, _section_cutout


def test_neptune_windows_and_template_detector_preference() -> None:
    assert [window_id(mjd) for mjd in (60842.38, 61017.78, 61208.52)] == [1, 2, 3]
    candidates = [
        {"mjd": 61209.0, "detector": 1, "file_url": "https://example.org/a.fits"},
        {"mjd": 61210.0, "detector": 2, "file_url": "https://example.org/b.fits"},
        {"mjd": 61211.0, "detector": 2, "file_url": "https://example.org/c.fits"},
        {"mjd": 61020.0, "detector": 2, "file_url": "https://example.org/d.fits"},
    ]
    selected = select_templates(candidates, 2)
    assert [row["detector"] for row in selected] == [2, 2, 1]


def test_neptune_central_flag_fractions_and_cloud_key() -> None:
    flags = np.zeros((9, 9), dtype=np.uint32)
    flags[2, 2] = 333057605
    flags[4, 4] = 67141634
    assert central_fractions(flags) == pytest.approx((1 / 25, 1 / 25))
    assert _cloud_location('{"aws": {"bucket": "nasa-irsa-spherex", "key": "dr1/a.fits"}}') == (
        "nasa-irsa-spherex", "dr1/a.fits")


def test_cloud_section_preserves_cropped_spatial_wcs(tmp_path: Path) -> None:
    spatial = WCS(naxis=2)
    spatial.wcs.crpix = [10, 10]
    spatial.wcs.crval = [2.0, 0.0]
    spatial.wcs.cdelt = [-0.001, 0.001]
    spatial.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    header = spatial.to_header()
    header["CRPIX1W"] = 10.0
    header["CRPIX2W"] = 10.0
    image = np.arange(400, dtype=np.float32).reshape(20, 20)
    hdus = [fits.PrimaryHDU()]
    for name in ("IMAGE", "FLAGS", "VARIANCE", "ZODI"):
        hdus.append(fits.ImageHDU(image.copy(), header=header, name=name))
    hdus.append(fits.BinTableHDU.from_columns([], name="WCS-WAVE"))
    source_path = tmp_path / "full.fits"
    fits.HDUList(hdus).writeto(source_path)
    target = tmp_path / "section.fits"
    with fits.open(source_path) as source:
        _section_cutout(source, 2.0, 0.0, 5 * 6.15 / 3600, target)
    with fits.open(target) as result:
        assert result["IMAGE"].data.shape == (5, 5)
        assert result["FLAGS"].data.shape == (5, 5)
        x, y = WCS(result["IMAGE"].header).world_to_pixel_values(2.0, 0.0)
        assert (x, y) == pytest.approx((2.0, 2.0))
        assert result["IMAGE"].header["CRPIX1W"] == 3.0


def test_http_503_uses_cloud_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    response = requests.Response()
    response.status_code = 503
    def unavailable(*args, **kwargs):
        raise requests.HTTPError("503", response=response)
    monkeypatch.setattr(io.requests, "get", unavailable)
    monkeypatch.setattr(io.time, "sleep", lambda seconds: None)
    called = []
    def write_cloud(row, ra_deg, dec_deg, size_deg, destination):
        called.append((row["cloud_key"], ra_deg, dec_deg))
        destination.write_bytes(b"section")
    monkeypatch.setattr(io, "_cloud_cutout", write_cloud)
    row = {"file_url": "https://example.org/frame.fits",
           "cloud_bucket": "nasa-irsa-spherex", "cloud_key": "dr1/frame.fits"}
    path = io.fetch_cutout(row, 2.0, 0.0, 0.1, tmp_path)
    assert path is not None and path.read_bytes() == b"section"
    assert called == [("dr1/frame.fits", 2.0, 0.0)]
