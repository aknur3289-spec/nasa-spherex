# P06 — `pipeline/spx/moving.py`: frames of Neptune, Uranus + empty-sky control (data for the science lead / Distance Dial)
Tool: Claude Code (real queries, iterative). Branch: `data/moving`. Start right after P01 is merged (can run in background while you do P05).

---
Read AGENTS.md and docs/DATA.md. The science lead needs, for each control body, every SPHEREx exposure that actually contains the body at the exposure time, with ephemeris truth attached. You fetch and package the data; you do NOT implement the dial geometry (that is `pipeline/spx/geometry.py`, owned by the science lead — do not edit it).

FILES
- `pipeline/spx/moving.py`, `pipeline/fetch_moving.py` (CLI), `pipeline/tests/test_moving.py`
- outputs `data/meta/<target_id>/epochs.csv`, `data/meta/<target_id>/passes.json`, `data/meta/<target_id>/HANDOFF.md`, `data/meta/<target_id>/contact.png`

API
```python
def ephemeris(body: str, mjd: np.ndarray, source: str = "horizons") -> pd.DataFrame
    # columns: mjd, ra_deg, dec_deg, delta_au (observer distance), r_au (heliocentric), elong_deg, source
    # horizons: astroquery.jplhorizons, location='500' (geocentric; SPHEREx LEO parallax is negligible at >5 AU)
    # fallback 'astropy': astropy.coordinates.get_body (builtin) → ICRS; record source='astropy-builtin'
def find_exposures(body: str, mjd_start: float, mjd_end: float, detectors: list[int],
                   window_days: float = 7.0) -> pd.DataFrame
    # weekly windows: ephemeris at window mid → TAP with
    #   1 = INTERSECTS(CIRCLE('ICRS', ra, dec, r_deg), p.poly) AND p.time_bounds_lower BETWEEN t0 AND t1
    # r_deg = body motion over the window + 0.1 deg margin. Then for EACH returned row compute the
    # ephemeris at that row's own MJD and keep it only if that position is inside the footprint
    # (download-free check: use p.poly if parseable, else keep and verify after cutout).
def fetch_moving(target_id: str, body: str, size_deg: float, detectors: list[int],
                 lat_offset_deg: float = 0.0, max_workers: int = 6) -> Path
    # cutout centred on the ephemeris position AT THE EXPOSURE TIME (+ ecliptic-latitude offset for the control)
```

TARGETS (put them in fields.yaml under `moving:`)
- `neptune` (body "Neptune", detectors 1 2 3, size 10′)
- `uranus` (body "Uranus", same)
- `neptune-blank` = same exposures' times and detectors as neptune but position shifted +1.0° in ecliptic latitude (convert via `GeocentricTrueEcliptic`, add offset, back to ICRS). Must use the SAME pass windows.
Mission span: from the earliest to the latest MJD available in dr1+qr3 (get it from discovery; do not assume).

epochs.csv = the P02 columns + body, eph_ra_deg, eph_dec_deg, delta_au, r_au, elong_deg, eph_source, lat_offset_deg, target_saturated (any saturation-type BAD bit within 2 px of the target).
passes.json = survey passes (assign_survey_pass) with: mid MJD/UTC, n exposures per detector, mean elongation, which side of quadrature (elongation east/west). The dial needs one reference pass and the next pass ~6 months later; list all valid (A, B) pass combinations with dt.
contact.png = for each pass, 6 thumbnails centred on the ephemeris position with a crosshair (quick visual proof the body is there).
HANDOFF.md (for the science lead, ≤ 30 lines): what was fetched, counts per pass and detector, which passes are near quadrature, saturation status, ephemeris source, known problems, exact paths.

RULES
- Truth (ephemeris) is ONLY recorded as metadata for validation — never used to choose dial predictions. Keep it in separate columns with eph_ prefix.
- Neptune/Uranus will likely be saturated/flagged at the core: that is expected; report it, do not drop those frames (geometry still works).
- Cache: same rules as io.py. Network only via io.py functions + Horizons.

TESTS (offline): ecliptic offset of +1° round-trips; window radius covers motion; a synthetic footprint test for inside/outside.

DONE: neptune, uranus, neptune-blank fetched; HANDOFF.md written; message to the science lead with the paths and pass table.
