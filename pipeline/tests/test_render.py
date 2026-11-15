from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest
from astropy.wcs import WCS
from PIL import Image

from spx.render import diff_png, field_grid, mask_png, stretch_params, to_grid, to_png
from pipeline.build_color import compose


@dataclass
class FrameStub:
    image: np.ndarray
    bad: np.ndarray
    wcs: WCS


def test_field_grid_is_odd_and_centered() -> None:
    wcs, shape = field_grid(210.80227, 54.34895, 10)
    assert shape == (99, 99)
    x, y = wcs.world_to_pixel_values(210.80227, 54.34895)
    assert (x, y) == pytest.approx((49, 49), abs=1e-7)
    assert wcs.wcs.cdelt[0] < 0 < wcs.wcs.cdelt[1]


def test_rotated_frame_point_lands_on_grid() -> None:
    source_wcs = WCS(naxis=2)
    source_wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    source_wcs.wcs.crval = [210.80227, 54.34895]
    source_wcs.wcs.crpix = [17, 17]
    theta = np.deg2rad(27)
    pixel_deg = 6.15 / 3600
    source_wcs.wcs.cd = pixel_deg * np.array(
        [[-np.cos(theta), np.sin(theta)], [np.sin(theta), np.cos(theta)]]
    )
    image = np.zeros((33, 33), dtype=np.float32)
    image[14, 20] = 100
    frame = FrameStub(image, np.zeros_like(image, dtype=bool), source_wcs)
    grid_wcs, shape = field_grid(210.80227, 54.34895, 4)
    projected, bad = to_grid(frame, grid_wcs, shape)
    source_ra, source_dec = source_wcs.pixel_to_world_values(20, 14)
    expected_x, expected_y = grid_wcs.world_to_pixel_values(source_ra, source_dec)
    peak_y, peak_x = np.unravel_index(np.nanargmax(projected), projected.shape)
    assert abs(peak_x - expected_x) <= 1
    assert abs(peak_y - expected_y) <= 1
    assert not bad[peak_y, peak_x]


def test_stretch_shared_across_backgrounds(tmp_path: Path) -> None:
    signal = np.arange(100, dtype=np.float32).reshape(10, 10)
    first, second = signal + 20, signal + 120
    stretch = stretch_params([first, second])
    first_meta = to_png(first, np.zeros_like(first, dtype=bool), stretch, tmp_path / "a.png")
    second_meta = to_png(second, np.zeros_like(second, dtype=bool), stretch, tmp_path / "b.png")
    for key in ("kind", "lo", "hi", "unit"):
        assert first_meta[key] == second_meta[key] == stretch[key]
    assert second_meta["median_subtracted_mjysr"] - first_meta["median_subtracted_mjysr"] == 100
    assert (tmp_path / "a.png").read_bytes() == (tmp_path / "b.png").read_bytes()


def test_display_inpaints_mask_but_keeps_outside_transparent(tmp_path: Path) -> None:
    image = np.arange(25, dtype=np.float32).reshape(5, 5)
    bad = np.zeros_like(image, dtype=bool)
    bad[2, 2] = True
    image[0, 0] = np.nan
    footprint = np.ones_like(bad)
    footprint[0, 0] = False
    stretch = stretch_params([image])
    out = tmp_path / "sky.png"
    to_png(image, bad, stretch, out, scale=2, footprint=footprint)
    first_bytes = out.read_bytes()
    to_png(image, bad, stretch, out, scale=2, footprint=footprint)
    assert out.read_bytes() == first_bytes
    with Image.open(out) as png:
        assert png.size == (10, 10)
        pixels = np.asarray(png)
    assert pixels[4:6, 4:6, 3].min() == 255
    assert pixels[0:2, 0:2, 3].max() == 0
    assert pixels[6, 6, 3] == 255
    mask_png(bad, footprint, tmp_path / "mask.png")
    with Image.open(tmp_path / "mask.png") as png:
        overlay = np.asarray(png)
    assert (overlay[2, 2] == [255, 255, 255, 255]).all()
    assert overlay[0, 0, 3] == 0
    assert overlay[3, 3, 3] == 0


def test_color_composite_uses_ordered_medians_and_common_stretch() -> None:
    blue = [np.array([[1.0, np.nan], [2.0, 3.0]]), np.array([[3.0, np.nan], [4.0, 5.0]])]
    green = [np.array([[5.0, np.nan], [6.0, 7.0]])]
    red = [np.array([[9.0, np.nan], [10.0, 11.0]])]
    rgba = compose([blue, green, red])
    assert rgba.shape == (2, 2, 4)
    assert (rgba[0, 0, :3] == sorted(rgba[0, 0, :3], reverse=True)).all()
    assert rgba[0, 1, 3] == 0
    assert rgba[1, 0, 3] == 255


def test_identical_images_have_neutral_difference(tmp_path: Path) -> None:
    image = np.arange(100, dtype=np.float32).reshape(10, 10) + 1
    bad = np.zeros_like(image, dtype=bool)
    result = diff_png(image, image, bad, tmp_path / "diff.png", noise=2)
    assert result["scale_b"] == pytest.approx(1)
    with Image.open(tmp_path / "diff.png") as png:
        pixels = np.asarray(png)
    assert np.all(pixels[..., :3] == 128)
    assert np.all(pixels[..., 3] == 255)


def test_all_nan_image_raises(tmp_path: Path) -> None:
    image = np.full((2, 2), np.nan)
    with pytest.raises(ValueError, match="no finite pixels"):
        stretch_params([image])
    with pytest.raises(ValueError, match="no finite unmasked pixels"):
        to_png(image, np.zeros((2, 2), dtype=bool),
               {"kind": "asinh", "lo": 0, "hi": 1, "unit": "MJy/sr"},
               tmp_path / "none.png")
