"""pytest pipeline/tests — run after ANY change to geometry, pairing or signal code."""
import sys
from pathlib import Path

import numpy as np
from astropy.time import Time
import astropy.units as u

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spx.geometry import predict_radec, fit_distance, ang_sep_deg  # noqa: E402
from spx.horizons import _from_astropy  # noqa: E402
from spx.detectability import apparent_mag, max_distance_au  # noqa: E402
from spx.focus import dial_grid  # noqa: E402


def _two_epochs(body, t0="2025-06-10"):
    t0 = Time(t0)
    t1 = t0 + 182.6 * u.day
    e0, e1 = _from_astropy(body, Time([t0, t1]))
    return t0, t1, e0, e1


def test_identity_at_t0():
    t = Time("2025-06-10")
    p = predict_radec(10.0, 5.0, t, 100.0, t)[0]
    assert ang_sep_deg(p[0], p[1], 10.0, 5.0) * 3600 < 0.01


def test_neptune_distance_recovered_within_15pct():
    t0, t1, e0, e1 = _two_epochs("neptune")
    d, off, _ = fit_distance(e0["ra_deg"], e0["dec_deg"], t0, e1["ra_deg"], e1["dec_deg"], t1)
    assert abs(d - e0["r_au"]) / e0["r_au"] < 0.15
    assert np.nanmin(off) < 20 * 6.15  # within 20 SPHEREx pixels


def test_uranus_positive_control():
    t0, t1, e0, e1 = _two_epochs("uranus", "2025-08-15")
    d, _, _ = fit_distance(e0["ra_deg"], e0["dec_deg"], t0, e1["ra_deg"], e1["dec_deg"], t1)
    assert abs(d - e0["r_au"]) / e0["r_au"] < 0.15


def test_static_model_is_wrong():
    t0, t1, e0, e1 = _two_epochs("neptune")
    d, _, _ = fit_distance(e0["ra_deg"], e0["dec_deg"], t0, e1["ra_deg"], e1["dec_deg"], t1, orbit="static")
    assert abs(d - e0["r_au"]) / e0["r_au"] > 0.15


def test_detectability_sanity():
    assert abs(float(apparent_mag(49528, 0.41, 30)) - 7.8) < 0.3   # Neptune V ≈ 7.8
    assert 300 < max_distance_au(49528, 0.41, 1) < 380           # plan: ≈ 340 AU
    assert max_distance_au(49528, 0.41, 100) > max_distance_au(49528, 0.41, 1)


def test_dial_grid_is_fine_enough():
    g = dial_grid(15, 1000, step_px=15)
    shift_px = 72600.0 / g
    assert np.max(np.abs(np.diff(shift_px))) <= 15.01


def test_ang_sep_broadcasts_scalar_vs_array():
    d = ang_sep_deg(10.0, 5.0, np.array([10.0, 11.0, 10.0, 10.0, 12.0]), np.array([5.0, 5.0, 6.0, 4.0, 5.0]))
    assert d.shape == (5,)
    assert abs(d[0]) < 1e-9 and abs(d[2] - 1.0) < 1e-9
    assert abs(float(ang_sep_deg(0, 0, 0, 1)) - 1.0) < 1e-9
