"""Parallax geometry for the Distance Dial.

Model: an object seen at (ra0, dec0) from Earth at time t0 is assumed to sit at
heliocentric distance d_au on a circular, prograde orbit about the ecliptic pole.
We place it on the line of sight at |r| = d, then rotate it by the Keplerian mean
motion and look at it again from Earth's position at each later time.

Units: angles in degrees, distances in AU, times as astropy Time (TDB).
Ephemeris: astropy "builtin" (no network). Geocentric observer; SPHEREx sits in
low Earth orbit, whose ~7000 km offset is negligible for d >= 5 AU.
"""
from __future__ import annotations

import numpy as np
from astropy.time import Time
from astropy.coordinates import get_body_barycentric, solar_system_ephemeris
import astropy.units as u

OBLIQUITY_DEG = 23.4392911  # J2000 mean obliquity
_eps = np.radians(OBLIQUITY_DEG)
# ICRS (equatorial) -> ecliptic rotation about the x axis
R_EQ2ECL = np.array([[1, 0, 0],
                     [0, np.cos(_eps), np.sin(_eps)],
                     [0, -np.sin(_eps), np.cos(_eps)]])
R_ECL2EQ = R_EQ2ECL.T
YEAR_DAYS = 365.25


def _unit(ra_deg, dec_deg):
    ra, dec = np.radians(ra_deg), np.radians(dec_deg)
    return np.array([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)])


def _radec(vec):
    """Equatorial vector(s) [..., 3] -> (ra_deg, dec_deg)."""
    vec = np.asarray(vec)
    x, y, z = vec[..., 0], vec[..., 1], vec[..., 2]
    ra = np.degrees(np.arctan2(y, x)) % 360.0
    dec = np.degrees(np.arctan2(z, np.hypot(x, y)))
    return ra, dec


def earth_helio_ecl(times: Time) -> np.ndarray:
    """Heliocentric ecliptic position of Earth, AU, shape [N, 3]."""
    with solar_system_ephemeris.set("builtin"):
        e = get_body_barycentric("earth", times).xyz.to(u.AU).value
        s = get_body_barycentric("sun", times).xyz.to(u.AU).value
    return (R_EQ2ECL @ (e - s)).T.reshape(-1, 3)


def place_on_sphere(ra0: float, dec0: float, t0: Time, d_au: float) -> np.ndarray | None:
    """Heliocentric ecliptic position of a body seen at (ra0, dec0) at distance d_au.

    Returns None if the line of sight never reaches heliocentric distance d_au.
    """
    E = earth_helio_ecl(t0)[0]
    uvec = R_EQ2ECL @ _unit(ra0, dec0)
    b = E @ uvec
    disc = b * b - (E @ E - d_au ** 2)
    if disc < 0:
        return None
    s = -b + np.sqrt(disc)  # far root: the body is beyond Earth
    return E + s * uvec


def predict_radec(ra0: float, dec0: float, t0: Time, d_au: float, times: Time,
                  orbit: str = "circular") -> np.ndarray:
    """Predicted geocentric (ra_deg, dec_deg) at `times` for an object at d_au.

    orbit: "circular" (parallax + circular prograde orbit about the ecliptic pole)
           or "static" (parallax only; the known-wrong baseline from the plan).
    Returns array [N, 2]; rows are NaN if d_au is unreachable along the line of sight.
    """
    times = Time(np.atleast_1d(times.jd), format="jd", scale=times.scale)
    P0 = place_on_sphere(ra0, dec0, t0, d_au)
    if P0 is None:
        return np.full((len(times), 2), np.nan)
    dt = (times.tdb.jd - t0.tdb.jd)
    if orbit == "circular":
        n = 2 * np.pi / (d_au ** 1.5 * YEAR_DAYS)  # rad / day
        ang = n * dt
    elif orbit == "static":
        ang = np.zeros_like(dt)
    else:
        raise ValueError(orbit)
    c, s = np.cos(ang), np.sin(ang)
    P = np.stack([c * P0[0] - s * P0[1], s * P0[0] + c * P0[1], np.full_like(c, P0[2])], -1)
    E = earth_helio_ecl(times)
    los_eq = (R_ECL2EQ @ (P - E).T).T
    ra, dec = _radec(los_eq)
    return np.stack([ra, dec], -1)


def ang_sep_deg(ra1, dec1, ra2, dec2):
    """Great-circle separation, degrees (vectorised)."""
    a, b = _unit(ra1, dec1), _unit(ra2, dec2)
    return np.degrees(np.arctan2(np.linalg.norm(np.cross(a, b, axis=0), axis=0),
                                 np.sum(a * b, axis=0)))


def solar_elongation_deg(ra, dec, t: Time) -> float:
    """Sun–Earth–target angle in degrees (SPHEREx observes near 90°)."""
    E = earth_helio_ecl(t)[0]
    to_sun = -E / np.linalg.norm(E)
    los = R_EQ2ECL @ _unit(ra, dec)
    return float(np.degrees(np.arccos(np.clip(to_sun @ los, -1, 1))))


def fit_distance(ra0, dec0, t0: Time, ra1, dec1, t1: Time,
                 d_grid=None, orbit="circular"):
    """Blind distance recovery from two positions. Returns (best_d, offsets_arcsec, d_grid)."""
    if d_grid is None:
        d_grid = np.geomspace(3, 1000, 2000)
    off = []
    for d in d_grid:
        p = predict_radec(ra0, dec0, t0, d, t1, orbit)[0]
        off.append(np.nan if np.isnan(p[0]) else ang_sep_deg(p[0], p[1], ra1, dec1) * 3600)
    off = np.array(off)
    return float(d_grid[np.nanargmin(off)]), off, d_grid
