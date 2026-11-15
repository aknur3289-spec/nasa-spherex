from pipeline.build_neptune_track import longest_fixed_window


def test_longest_fixed_window_handles_ra_wrap() -> None:
    rows = [
        {"mjd": "1", "eph_ra": "359.95", "eph_dec": "0"},
        {"mjd": "2", "eph_ra": "0.00", "eph_dec": "0"},
        {"mjd": "3", "eph_ra": "0.04", "eph_dec": "0"},
        {"mjd": "4", "eph_ra": "1.00", "eph_dec": "0"},
    ]
    assert [row["mjd"] for row in longest_fixed_window(rows)] == ["1", "2", "3"]
