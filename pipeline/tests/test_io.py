"""Offline checks for SPHEREx catalog and cutout handling."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest
import requests
from astropy.io import fits
from astropy.table import Table
from astropy.wcs import WCS

from pipeline.spx import io


def row(name: str = "level2_foo_spx_l2b-v27-2026-196.fits", **changes) -> dict:
    value = {
        "file_url": f"https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/{name}",
        "uri": f"ibe/data/spherex/dr1/{name}", "collection": "spherex_dr1",
        "mjd": 60805.0, "detector": 2, "bandpassname": "SPHEREx-D2",
        "planeid": "plane", "obs_id": "obs",
    }
    value.update(changes)
    return value


def make_fits(path: Path, size: int = 98) -> None:
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [(size + 1) / 2, (size + 1) / 2]
    wcs.wcs.cdelt = [-6.15 / 3600, 6.15 / 3600]
    wcs.wcs.crval = [210.80227, 54.34895]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    fits.HDUList([
        fits.PrimaryHDU(),
        fits.ImageHDU(np.zeros((size, size), dtype=np.float32), header=wcs.to_header(), name="IMAGE"),
        fits.ImageHDU(np.zeros((size, size), dtype=np.float32), name="WCS-WAVE"),
    ]).writeto(path)


def test_cutout_url_and_filename() -> None:
    item = row()
    assert io.cutout_url(item["file_url"], 210.80227, 54.34895, 1 / 6).endswith(
        "?center=210.80227,54.34895d&size=0.16666666666666666"
    )
    assert io._local_path(item, 210.80227, 54.34895, 1 / 6, Path("data/raw/m101")).name == (
        "level2_foo_spx_l2b-v27-2026-196__c210.80227_+54.34895_s0.1667.fits"
    )


def test_cache_hit_never_downloads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    item = row()
    path = io._local_path(item, 210.80227, 54.34895, 1 / 6, tmp_path)
    make_fits(path)
    calls = []
    monkeypatch.setattr(io.requests, "get", lambda *args, **kwargs: calls.append(args))
    assert io.fetch_cutout(item, 210.80227, 54.34895, 1 / 6, tmp_path) == path
    assert calls == []


def test_download_removes_epsf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.fits"
    make_fits(source)
    with fits.open(source) as hdul:
        hdul.append(fits.ImageHDU(np.ones((2, 2)), name="EPSF"))
        hdul.writeto(source, overwrite=True)
    payload = source.read_bytes()
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, size):
            yield payload

    def get(url, **kwargs):
        calls.append(url)
        return Response()

    monkeypatch.setattr(io.requests, "get", get)
    target = io.fetch_cutout(row(), 210.80227, 54.34895, 1 / 6, tmp_path / "raw")
    assert len(calls) == 1 and target is not None
    with fits.open(target) as hdul:
        assert [hdu.name for hdu in hdul] == ["PRIMARY", "IMAGE", "WCS-WAVE"]
    assert not target.with_name(target.name + ".part").exists()


def test_http_retry_policy() -> None:
    error = requests.HTTPError("not found")
    error.response = requests.Response()
    error.response.status_code = 404
    assert not io._retryable(error)
    error.response.status_code = 503
    assert io._retryable(error)


def test_dedup_prefers_processing_version_then_dr1() -> None:
    qr3 = row("level2_a_spx_l2b-v28-2026-100.fits", collection="spherex_qr3")
    dr1_old = row("level2_a_spx_l2b-v27-2026-200.fits")
    assert io._deduplicate([dr1_old, qr3]) == [qr3]
    dr1_same = row("level2_a_spx_l2b-v28-2026-100.fits")
    assert io._deduplicate([qr3, dr1_same]) == [dr1_same]


def test_limit_spreads_across_time() -> None:
    rows = [row(mjd=float(n), obs_id=str(n)) for n in range(100)]
    assert [item["mjd"] for item in io._spread(rows, 3)] == [0.0, 50.0, 99.0]


def test_partial_area_and_outside(tmp_path: Path) -> None:
    small = tmp_path / "small.fits"
    make_fits(small, 40)
    assert io._validate(small, 210.80227, 54.34895, 1 / 6) == "partial"
    full = tmp_path / "full.fits"
    make_fits(full)
    assert io._validate(full, 210.80227, 54.34895, 1 / 6) == "ok"
    assert io._validate(full, 30, 10, 1 / 6) == "outside"


def test_tap_uses_real_columns_and_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    columns = {
        "file_url": [row()["file_url"]], "uri": [row()["uri"]],
        "time_bounds_lower": [60805.0], "energy_bandpassname": ["SPHEREx-D2"],
        "planeid": ["plane"], "obsid": ["obs"], "provenance_version": ["27.0"],
    }
    queries = []

    class Result:
        def to_table(self):
            return Table(columns)

    def query(query_text):
        queries.append(query_text)
        return Result()

    monkeypatch.setattr(io.Irsa, "query_tap", query)
    found = io.search_frames(210.80227, 54.34895, [2], mjd_range=(60800, 60810))
    assert len(found) == 1 and found[0]["obs_id"] == "obs"
    assert "SPHEREx-D2" in queries[0] and "BETWEEN 60800.0 AND 60810.0" in queries[0]


def test_field_index_with_cached_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    item = row()
    path = io._local_path(item, 210.80227, 54.34895, 1 / 6, Path("data/raw/m101"))
    path.parent.mkdir(parents=True)
    make_fits(path)
    monkeypatch.setattr(io, "search_frames", lambda *args, **kwargs: [item])
    index = io.fetch_field("m101", 210.80227, 54.34895, 1 / 6, [2], 2)
    with index.open(newline="") as source:
        records = list(csv.DictReader(source))
    assert records[0]["status"] == "cached"
    assert len(records[0]["sha256"]) == 64
    assert "downloaded=0 cached=1 failed=0" in capsys.readouterr().out
