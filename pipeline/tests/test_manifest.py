import json
from pathlib import Path

import pytest

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
