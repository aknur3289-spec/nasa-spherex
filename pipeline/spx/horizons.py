"""Ephemerides for known bodies: JPL Horizons first, astropy builtin as fallback.

Returns geocentric astrometric RA/Dec (deg), geocentric distance delta (AU) and
heliocentric distance r (AU). Horizons IDs: Uranus barycentre 7 / body 799,
Neptune 8 / 899, Pluto 999. location "500" = geocentre (good enough for SPHEREx in LEO).

Usage:
    from spx.horizons import ephem
    eph = ephem("neptune", ["2025-06-01", "2025-12-01"])
"""
from __future__ import annotations

import numpy as np
from astropy.time import Time
import astropy.units as u

HORIZONS_ID = {"uranus": "799", "neptune": "899", "pluto": "999", "saturn": "699", "jupiter": "599"}


def _from_horizons(body: str, times: Time) -> list[dict]:
    from astroquery.jplhorizons import Horizons
    obj = Horizons(id=HORIZONS_ID.get(body, body), location="500", epochs=list(times.utc.jd),
                   id_type=None)
    eph = obj.ephemerides(quantities="1,19,20,23")  # astrometric RA/Dec, r, delta, elongation
    return [{"jd_utc": float(row["datetime_jd"]), "ra_deg": float(row["RA"]), "dec_deg": float(row["DEC"]),
             "r_au": float(row["r"]), "delta_au": float(row["delta"]), "elong_deg": float(row["elong"]),
             "source": "JPL Horizons"} for row in eph]


def _from_astropy(body: str, times: Time) -> list[dict]:
    from astropy.coordinates import get_body, get_body_barycentric, solar_system_ephemeris
    out = []
    with solar_system_ephemeris.set("builtin"):
        for t in times:
            c = get_body(body, t)  # GCRS: geocentric, ICRS-aligned
            r = (get_body_barycentric(body, t) - get_body_barycentric("sun", t)).norm().to(u.AU).value
            out.append({"jd_utc": float(t.utc.jd), "ra_deg": float(c.ra.deg), "dec_deg": float(c.dec.deg),
                        "r_au": float(r), "delta_au": float(c.distance.to(u.AU).value),
                        "elong_deg": None, "source": "astropy builtin ephemeris"})
    return out


def ephem(body: str, times) -> list[dict]:
    times = Time(np.atleast_1d(times))
    try:
        return _from_horizons(body.lower(), times)
    except Exception as exc:  # network blocked, rate limit, etc.
        print(f"[horizons] falling back to astropy: {exc!r}")
        return _from_astropy(body.lower(), times)


if __name__ == "__main__":
    for row in ephem("neptune", ["2025-06-01", "2025-12-01"]):
        print(row)
