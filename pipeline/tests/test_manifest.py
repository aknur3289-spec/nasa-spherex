import json
from pathlib import Path

import pytest
from PIL import Image

from pipeline.spx.manifest import update_index, validate_field, write_field


@pytest.fixture
def field(tmp_path: Path) -> tuple[dict, Path]:
    sample = json.loads((Path(__file__).resolve().parents[2] / "web/public/data/demo/field.json").read_text())
    directory = tmp_path / "demo"
    directory.mkdir()
    for frame in sample["frames"]:
        (directory / frame["png"]).write_bytes(b"png")
    return sample, directory


def test_valid_field_and_index(field: tuple[dict, Path]) -> None:
    sample, directory = field
    validate_field(sample, directory)
    write_field(sample, directory)
    update_index(directory.parent)
    assert json.loads((directory.parent / "index.json").read_text()) == []


def test_missing_source_url(field: tuple[dict, Path]) -> None:
    sample, directory = field
    del sample["frames"][0]["source_url"]
    with pytest.raises(ValueError, match=r"\$\.frames\[0\]"):
        validate_field(sample, directory)


@pytest.mark.parametrize("missing", ["collection", "downloaded_utc"])
def test_real_frame_requires_own_provenance(field: tuple[dict, Path], missing: str) -> None:
    sample, _ = field
    sample["schema_version"] = "1.1"
    sample["provenance"]["synthetic"] = False
    for frame in sample["frames"]:
        frame.update(width_px=3, height_px=4, collection="spherex_dr1",
                     downloaded_utc="2026-11-14T08:00:00Z",
                     source_url="https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/test.fits")
    validate_field(sample)
    del sample["frames"][0][missing]
    with pytest.raises(ValueError, match=rf"\$\.frames\[0\]\.{missing}"):
        validate_field(sample)


def test_real_collection_matches_source_url(field: tuple[dict, Path]) -> None:
    sample, _ = field
    sample["schema_version"] = "1.1"
    sample["provenance"]["synthetic"] = False
    for frame in sample["frames"]:
        frame.update(width_px=3, height_px=4, collection="spherex_dr1",
                     downloaded_utc="2026-11-14T08:00:00Z",
                     source_url="https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/test.fits")
    sample["frames"][0]["collection"] = "spherex_qr3"
    with pytest.raises(ValueError, match=r"\$\.frames\[0\]\.collection"):
        validate_field(sample)


def test_missing_pair_endpoint(field: tuple[dict, Path]) -> None:
    sample, directory = field
    sample["pairs"][0]["b"] = "absent"
    with pytest.raises(ValueError, match=r"\$\.pairs\[0\]"):
        validate_field(sample, directory)


def test_missing_png(field: tuple[dict, Path]) -> None:
    sample, directory = field
    (directory / sample["frames"][0]["png"]).unlink()
    with pytest.raises(ValueError, match=r"\$\.frames\[0\]\.png"):
        validate_field(sample, directory)


def test_wrong_trust_and_real_fixture(field: tuple[dict, Path]) -> None:
    sample, directory = field
    sample["pairs"][0]["trust"] = "low"
    with pytest.raises(ValueError, match="trust"):
        validate_field(sample, directory)
    sample["pairs"][0]["trust"] = "high"
    with pytest.raises(ValueError, match="synthetic"):
        validate_field(sample, directory, real_build=True)


@pytest.mark.parametrize("location", ["description", "doi", "band"])
def test_nonempty_text(field: tuple[dict, Path], location: str) -> None:
    sample, directory = field
    if location == "description":
        sample["description"] = ""
    elif location == "doi":
        sample["provenance"]["doi"] = ""
    else:
        sample["frames"][0]["band"] = ""
    with pytest.raises(ValueError):
        validate_field(sample, directory)


@pytest.mark.parametrize("change", ["duplicate", "same", "trust", "source"])
def test_semantic_rejections(field: tuple[dict, Path], change: str) -> None:
    sample, directory = field
    if change == "duplicate":
        sample["frames"][1]["id"] = sample["frames"][0]["id"]
    elif change == "same":
        sample["pairs"][0]["b"] = sample["pairs"][0]["a"]
    elif change == "trust":
        sample["pairs"][0]["dlambda_frac"] = 0.5
    else:
        sample["provenance"]["synthetic"] = False
    with pytest.raises(ValueError):
        validate_field(sample, directory)


def test_v1_1_dimensions_and_diff(field: tuple[dict, Path]) -> None:
    sample, directory = field
    sample["schema_version"] = "1.1"
    for frame in sample["frames"]:
        Image.new("RGB", (3, 4)).save(directory / frame["png"])
        frame.update(width_px=3, height_px=4)
    pair = sample["pairs"][0]
    pair["diff_png"] = f"diff/{pair['a']}-{pair['b']}.png"
    (directory / "diff").mkdir()
    Image.new("RGB", (3, 4)).save(directory / pair["diff_png"])
    validate_field(sample, directory)
    sample["frames"][0]["width_px"] = 2
    with pytest.raises(ValueError, match="dimensions"):
        validate_field(sample, directory)
    sample["frames"][0]["width_px"] = 3
    Image.new("RGB", (4, 4)).save(directory / pair["diff_png"])
    with pytest.raises(ValueError, match="diff_png"):
        validate_field(sample, directory)


def test_color_asset_and_bands_are_strict(field: tuple[dict, Path]) -> None:
    sample, directory = field
    sample["schema_version"] = "1.1"
    for frame in sample["frames"]:
        Image.new("RGB", (3, 4)).save(directory / frame["png"])
        frame.update(width_px=3, height_px=4)
    sample["color_png"] = "color.png"
    sample["color_bands_um"] = [[0.75, 1.1], [1.1, 1.7], [1.7, 2.42]]
    with pytest.raises(ValueError, match="missing asset"):
        validate_field(sample, directory)
    Image.new("RGBA", (3, 4)).save(directory / "color.png")
    validate_field(sample, directory)
    sample["color_bands_um"][1] = [1.0, 1.7]
    with pytest.raises(ValueError, match="color_bands_um"):
        validate_field(sample, directory)
    sample["color_bands_um"][1] = [1.1, 1.7]
    Image.new("RGBA", (4, 4)).save(directory / "color.png")
    with pytest.raises(ValueError, match="dimensions"):
        validate_field(sample, directory)


def test_dial_bounds(field: tuple[dict, Path]) -> None:
    sample, directory = field
    sample["kind"] = "dial"
    sample["dial"] = {
        "reference_frame": sample["frames"][0]["id"], "model": "fixture",
        "search_radius_px": 1, "steps": [{
            "distance_au": 1, "frame": sample["frames"][0]["id"],
            "pred": sample["center"], "snr": 1, "offset_px": 0,
        }],
        "peak_distance_au": 1, "truth": {"distance_au": 1, "source": "fixture"},
        "negative_control_field": "other",
    }
    validate_field(sample, directory)
    for key, value in (("search_radius_px", 0), ("steps", [])):
        changed = json.loads(json.dumps(sample))
        changed["dial"][key] = value
        with pytest.raises(ValueError):
            validate_field(changed, directory)
    sample["dial"]["steps"][0]["offset_px"] = -1
    with pytest.raises(ValueError):
        validate_field(sample, directory)


def test_dial_outside_step_requires_all_nulls(field: tuple[dict, Path]) -> None:
    sample, directory = field
    sample["schema_version"] = "1.1"
    sample["kind"] = "dial"
    for frame in sample["frames"]:
        Image.new("RGB", (3, 4)).save(directory / frame["png"])
        frame.update(width_px=3, height_px=4)
    sample["dial"] = {
        "reference_frame": sample["frames"][0]["id"], "model": "fixture",
        "search_radius_px": 20, "steps": [{"distance_au": 20, "frame": None,
                                        "pred": sample["center"], "snr": None,
                                        "offset_px": None, "outside_frame": True},
                                       {"distance_au": 30, "frame": sample["frames"][0]["id"],
                                        "pred": sample["center"], "snr": 2,
                                        "offset_px": 1, "raw_peak_offset_px": 0.5}],
        "peak_distance_au": 30, "truth": {"distance_au": 30, "source": "fixture"},
        "negative_control_field": "other",
    }
    validate_field(sample, directory)
    sample["dial"]["steps"][0]["snr"] = 1
    with pytest.raises(ValueError, match="outside step"):
        validate_field(sample, directory)
    sample["dial"]["steps"][0]["snr"] = None
    sample["dial"]["peak_distance_au"] = 20
    with pytest.raises(ValueError, match="minimum covered offset"):
        validate_field(sample, directory)
