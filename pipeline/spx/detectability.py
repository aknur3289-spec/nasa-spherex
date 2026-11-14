"""Detectability Calculator: what SPHEREx can and cannot see.

Order-of-magnitude reflected-light model (same as the plan, section 6):
    V = H + 5 log10(r * Delta) (phase angle ignored; r ~ Delta ~ d at large d)
    H from diameter D [km] and geometric albedo p:  D = 1329 / sqrt(p) * 10**(-H/5)
    Stack gain for N frames: 2.5 log10(sqrt(N)) = 1.25 log10(N) mag
Caveats (say them on the slide): V is used as a proxy for near-IR AB, methane
absorption and thermal emission are ignored -> the real limit is worse.
"""
from __future__ import annotations

import json
import numpy as np

SINGLE_FRAME_LIMIT_AB = 18.4   # 5 sigma, R~41 channel; secondary source, verify in Explanatory Supplement
R_EARTH_KM = 6371.0

PRESETS = {
    # name: (diameter_km, geometric_albedo)
    "Neptune-size": (49528.0, 0.41),
    "Planet Nine (5 M_earth, ~2 R_earth, p=0.4)": (2 * 2 * R_EARTH_KM, 0.4),
    "Planet Nine (10 M_earth, ~3 R_earth, p=0.4)": (2 * 3 * R_EARTH_KM, 0.4),
    "Earth-size": (2 * R_EARTH_KM, 0.37),
    "Mars-size": (6779.0, 0.17),
    "Eris-size": (2326.0, 0.96),
}


def H_from_size(diameter_km: float, albedo: float) -> float:
    return 5 * np.log10(1329.0 / (diameter_km * np.sqrt(albedo)))


def apparent_mag(diameter_km: float, albedo: float, d_au):
    """V magnitude at heliocentric distance d_au, seen at opposition-like geometry (r ≈ Δ ≈ d)."""
    d = np.asarray(d_au, dtype=float)
    return H_from_size(diameter_km, albedo) + 5 * np.log10(d * np.maximum(d - 1.0, 1e-3))


def limit_mag(n_frames: int = 1, single=SINGLE_FRAME_LIMIT_AB) -> float:
    return single + 1.25 * np.log10(max(n_frames, 1))


def max_distance_au(diameter_km: float, albedo: float, n_frames: int = 1) -> float:
    """Largest d at which the body is brighter than the (stacked) limit."""
    grid = np.geomspace(5, 5000, 20000)
    m = apparent_mag(diameter_km, albedo, grid)
    ok = grid[m <= limit_mag(n_frames)]
    return float(ok.max()) if ok.size else float("nan")


def parallax_shift_arcmin(d_au):
    """Half-year shift from parallax alone at quadrature: baseline ~2 AU."""
    return np.degrees(2.0 / np.asarray(d_au)) * 60


def table(n_frames_list=(1, 100, 300)):
    rows = []
    for name, (D, p) in PRESETS.items():
        row = {"name": name, "diameter_km": D, "albedo": p, "H": round(float(H_from_size(D, p)), 2),
               "V_at_300au": round(float(apparent_mag(D, p, 300)), 2),
               "V_at_500au": round(float(apparent_mag(D, p, 500)), 2)}
        for n in n_frames_list:
            row[f"max_d_au_N{n}"] = round(max_distance_au(D, p, n), 0)
        rows.append(row)
    return rows


if __name__ == "__main__":
    print("Limits: N=1 ->", limit_mag(1), " N=100 ->", round(limit_mag(100), 2), " N=300 ->", round(limit_mag(300), 2))
    print("Neptune V at 30 AU (sanity, real ~7.8):", round(float(apparent_mag(49528, 0.41, 30)), 2))
    rows = table()
    for r in rows:
        print(r)
    grid = np.geomspace(20, 1500, 60)
    out = {"model": "reflected light, V≈AB proxy, phase ignored",
           "single_frame_limit_ab": SINGLE_FRAME_LIMIT_AB,
           "distances_au": [round(float(x), 2) for x in grid],
           "bodies": [{"name": n, "mag": [round(float(m), 2) for m in apparent_mag(D, p, grid)]}
                      for n, (D, p) in PRESETS.items()],
           "limits": {str(n): round(float(limit_mag(n)), 2) for n in (1, 4, 100, 300)},
           "table": rows}
    json.dump(out, open("limits.json", "w"), indent=1)
    print("wrote limits.json")
