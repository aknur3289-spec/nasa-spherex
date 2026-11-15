import csv
import json
import sys
import types
from pathlib import Path

import numpy as np
from astropy.io import fits
from PIL import Image

from pipeline import build_field as builder
from pipeline import spx
from pipeline.tests.test_frame import synthetic_mef


def test_offline_synthetic_build(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = Path("fields.yaml")
    config.write_text("""defaults:
  size_arcmin: 0.05
  detectors: [2]
  collections: [spherex_dr1]
  doi: synthetic
fields:
  - id: tiny
    enabled: true
    title: Tiny test
    description: Offline fixture
    ra: 210.0
    dec: 54.0
""")
    raw = Path("data/meta/tiny/raw_index.csv")
    raw.parent.mkdir(parents=True)
    paths = []
    for number, (mjd, wavelength_um) in enumerate(((60805, 1.31), (60806, 1.40),
                                                     (61005, 1.315), (61006, 1.48)), 1):
        path = Path(f"frame{number}.fits")
        synthetic_mef(path)
        with fits.open(path, mode="update") as hdul:
            hdul["IMAGE"].header["MJD-OBS"] = mjd
            hdul["IMAGE"].header["OBSID"] = f"fixture-{number}"
            hdul["IMAGE"].header["CRVAL1W"] = (wavelength_um - 0.01) * 1e-6
            hdul["FLAGS"].data[0, 0] = 1 << 21
            yy, xx = np.indices((3, 3))
            hdul["IMAGE"].data[:] = 5 + xx + yy + number * 0.1
        paths.append(path)
    with raw.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=("field_id", "collection", "source_url",
                                                    "local_path", "downloaded_utc", "status"))
        writer.writeheader()
        for path in paths:
            writer.writerow({"field_id": "tiny", "collection": "spherex_dr1",
                             "source_url": f"https://example.invalid/{path.name}",
                             "local_path": str(path), "downloaded_utc": "2026-11-14T08:00:00+00:00",
                             "status": "cached"})

    def write_png(image, bad, stretch, out, scale=1, footprint=None):
        Image.fromarray(np.full((3 * scale, 3 * scale, 4), 255, dtype=np.uint8), "RGBA").save(out)
        return stretch

    def write_mask(bad, footprint, out):
        out.parent.mkdir(parents=True, exist_ok=True)
        write_png(bad, bad, {}, out)

    fake_render = types.ModuleType("pipeline.spx.render")
    fake_render.field_grid = lambda ra, dec, size: (None, (3, 3))
    fake_render.to_grid_with_footprint = lambda frame, grid, shape: (
        frame.image, frame.bad, np.ones_like(frame.bad, dtype=bool))
    fake_render.stretch_params = lambda images: {"kind": "asinh", "lo": -1.0,
                                                 "hi": 5.0, "unit": "MJy/sr"}
    fake_render.to_png = write_png
    fake_render.mask_png = write_mask
    fake_render.diff_png = lambda a, b, bad, out, noise: write_png(a, bad, {}, out)
    monkeypatch.setitem(sys.modules, "pipeline.spx.render", fake_render)
    monkeypatch.setattr(spx, "render", fake_render, raising=False)
    monkeypatch.setattr(builder, "fetch_field", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("offline build called network")))
    monkeypatch.setattr(builder, "_commit", lambda: "synthetic-test")
    manifest = builder.build_field("tiny", offline=True, config_path=config,
                                   data_root=Path("web/public/data"), synthetic=True)
    assert len(manifest["frames"]) >= 2
    assert len(manifest["pairs"]) >= 2
    assert manifest["pairs"][0]["trust"] == "high"
    outdir = Path("web/public/data/tiny")
    assert manifest["schema_version"] == "1.1"
    assert manifest["provenance"]["downloaded_utc"] == "2026-11-14T08:00:00Z"
    assert all(frame["collection"] == "spherex_dr1" and
               frame["downloaded_utc"] == "2026-11-14T08:00:00Z"
               for frame in manifest["frames"])
    assert all(set(pair) == {"a", "b", "dlambda_frac", "dt_days", "trust", "diff_png"}
               for pair in manifest["pairs"])
    assert [pair["trust"] for pair in manifest["pairs"]] == sorted(
        (pair["trust"] for pair in manifest["pairs"]),
        key={"high": 0, "medium": 1, "low": 2}.__getitem__)
    assert all((outdir / pair["diff_png"]).is_file() for pair in manifest["pairs"])
    assert all((frame["width_px"], frame["height_px"]) == (3, 3)
               for frame in manifest["frames"])
    assert all((outdir / frame["mask_png"]).is_file() for frame in manifest["frames"])
    assert json.loads((outdir / "timeline.json").read_text()) == [
        {"frame_id": frame["id"], "obs_time_utc": frame["obs_time_utc"], "mjd": frame["mjd"]}
        for frame in sorted(manifest["frames"], key=lambda item: (item["obs_time_utc"], item["id"]))
    ]
    assert (Path("web/public/data/tiny") / "thumb.png").is_file()
    assert json.loads(Path("web/public/data/tiny/field.json").read_text()) == manifest
