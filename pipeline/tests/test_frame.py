"""Offline tests for SPHEREx frame metadata."""

import csv
import os
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from pipeline.spx.frame import (
    BAD_BITS, SAT_BITS, bad_mask, build_epochs, read_frame, sat_mask, wavelength_at,
)


def synthetic_mef(path: Path) -> None:
    spatial = WCS(naxis=2)
    spatial.wcs.crpix = [2, 2]
    spatial.wcs.crval = [210, 54]
    spatial.wcs.cdelt = [-0.001, 0.001]
    spatial.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    header = spatial.to_header()
    spectral = WCS(naxis=2, key="W")
    spectral.wcs.crpix = [1, 1]
    spectral.wcs.crval = [1.3e-6, 0.03e-6]
    spectral.wcs.cdelt = [0.01e-6, 0.001e-6]
    spectral.wcs.ctype = ["WAVE", "WAVE"]
    spectral.wcs.cunit = ["m", "m"]
    header.extend(spectral.to_header(key="W"))
    header["DETECTOR"] = 2
    header["OBSID"] = "test-observation"
    header["MJD-OBS"] = 60805.0
    flags = np.full((3, 3), 1 << 21, dtype=np.int32)
    flags[0, 0] |= 1 << 6
    flags[0, 1] |= 1 << 1
    flags[0, 2] |= 1 << 15
    flags[1, 0] |= 1 << 26
    flags[2, 0] |= 1 << 7
    flags[2, 1] |= 1 << 12
    flags[2, 2] |= 1 << 14
    flag_header = fits.Header()
    flag_header["MSKN0021"] = "SOURCE"
    flag_header["MSKN0006"] = "NONFUNC"
    flag_header["MSKN0001"] = "OVERFLOW"
    flag_header["MSKN0015"] = "NONLINEAR"
    flag_header["MSKN0026"] = "BLOOM"
    flag_header["MSKN0007"] = "DICHROIC"
    flag_header["MSKN0012"] = "FULLSAMPLE"
    flag_header["MSKN0014"] = "PHANMISS"
    fits.HDUList([
        fits.PrimaryHDU(header=fits.Header({"VERSION": "test"})),
        fits.ImageHDU(np.full((3, 3), 5, dtype=np.float32), header=header, name="IMAGE"),
        fits.ImageHDU(flags, header=flag_header, name="FLAGS"),
        fits.ImageHDU(np.ones((3, 3), dtype=np.float32), name="VARIANCE"),
        fits.ImageHDU(np.ones((3, 3), dtype=np.float32), name="ZODI"),
    ]).writeto(path)


def test_synthetic_frame(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.fits"
    synthetic_mef(path)
    frame = read_frame(path, 210, 54)
    assert frame.bad.sum() == 1
    assert frame.sat.sum() == 3
    assert np.isnan(frame.image[0, 0])
    assert frame.image[1, 1] == 4
    assert np.all(frame.image[[0, 0, 1, 2, 2, 2], [1, 2, 0, 0, 1, 2]] == 4)
    assert frame.meta["bad_pixel_fraction"] == pytest.approx(1 / 9)
    assert frame.meta["sat_pixel_fraction"] == pytest.approx(3 / 9)
    assert frame.meta["target_bad"] is True
    assert frame.meta["image_median_mjysr"] == 4
    assert frame.meta["noise_mad_mjysr"] == 0
    assert frame.meta["status"] == "ok"
    assert frame.meta["wavelength_um"] == pytest.approx(1.31)


def test_bad_bit_resolved_by_name() -> None:
    header = fits.Header({"MSKN0003": "NONFUNC", "MSKN0006": "SOURCE",
                          "MSKN0005": "OVERFLOW", "MSKN0004": "DICHROIC"})
    flags = np.array([[1 << 3, 1 << 6, 1 << 5, 1 << 4]], dtype=np.int32)
    assert bad_mask(flags, header).tolist() == [[True, False, False, False]]
    assert sat_mask(flags, header).tolist() == [[False, False, True, False]]


def test_bad_file_does_not_stop_field(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    directory = Path("data/meta/m101")
    directory.mkdir(parents=True)
    good = Path("good.fits")
    synthetic_mef(good)
    with (directory / "raw_index.csv").open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=(
            "field_id", "collection", "source_url", "local_path", "downloaded_utc", "status",
        ))
        writer.writeheader()
        for name in ("missing.fits", str(good)):
            writer.writerow({"field_id": "m101", "collection": "spherex_dr1",
                             "source_url": "https://example.org/cutout", "local_path": name,
                             "downloaded_utc": "2026-11-14T08:00:00Z", "status": "cached"})
    with build_epochs("m101", 210, 54).open(newline="") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 2
    assert [row["status"] for row in rows] == ["ok", "error"]
    assert [row["frame_id"] for row in rows] == ["f001", "f002"]
    assert float(rows[0]["sat_pixel_fraction"]) == pytest.approx(3 / 9)


def _real_cutout() -> Path:
    return Path(os.environ.get(
        "SPHEREX_REAL_CUTOUT",
        Path(__file__).resolve().parents[2] / "data/raw/m101_earliest_d2_cutout.fits",
    ))


@pytest.mark.real
def test_p00_wavelength() -> None:
    path = _real_cutout()
    if not path.exists():
        pytest.skip("P00 cutout is absent")
    with fits.open(path) as hdul:
        wavelength_um, _, x_pix, y_pix = wavelength_at(hdul, 210.80227, 54.34895)
    assert 1.10 <= wavelength_um <= 1.62
    assert wavelength_um == pytest.approx(1.506421284, abs=1e-6)
    assert (x_pix, y_pix) == pytest.approx((48.921068568, 48.498343663), abs=1e-6)


@pytest.mark.real
def test_p00_flag_policy_masks() -> None:
    path = _real_cutout()
    if not path.exists():
        pytest.skip("P00 cutout is absent")
    with fits.open(path) as hdul:
        header = hdul["FLAGS"].header
        flags = hdul["FLAGS"].data
        positions = {str(value).strip(): int(key[4:])
                     for key, value in header.items()
                     if key.startswith("MSKN") and key[4:].isdigit()}
        assert sum(1 << positions[name] for name in BAD_BITS) == 333057605
        assert sum(1 << positions[name] for name in SAT_BITS) == 67141634
        assert not (set(BAD_BITS) | set(SAT_BITS)) & {
            "SOURCE", "DICHROIC", "FULLSAMPLE", "PHANMISS"}
        bad = bad_mask(flags, header)
        sat = sat_mask(flags, header)
        assert bad.dtype == sat.dtype == bool
        assert bad.shape == sat.shape == flags.shape
