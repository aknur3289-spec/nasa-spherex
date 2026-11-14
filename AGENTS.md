# AGENTS.md — Data Engineering track, "Parallax Dial" (NASA Space Apps 2026, Planet X × SPHEREx)

Codex reads this file automatically. For Claude Code put a one-line `CLAUDE.md` in the repo root containing `@AGENTS.md`.

## Project in 5 lines
Public web tool showing how SPHEREx sky images change over time.
1. Honest Blink: compare only frame pairs taken at (almost) the same wavelength; every pair has a trust badge.
2. Distance Dial: re-centre pass-B frames on where an object at distance d would be; validated on Neptune/Uranus.
Architecture: offline Python pipeline -> static files `web/public/data/<field_id>/` (PNG + field.json) -> static Vite/React client. No backend.
**Pitch ≈ Sunday 15 Nov 2026, 13:00 Asia/Almaty; development ends overnight. DATA FREEZE: Sunday 01:30.**
Team of 3: **Data** (owner of this track), **Science** owner (= "science lead": geometry, PoC B, validation, all numbers on slides), **Frontend** owner (= "tech lead": repo, docs/CONTRACT.md, web/, deploy, merges into main). Prefer simple and working over clever.

## Data-track ownership (you may only touch these unless the prompt says otherwise)
- `pipeline/spx/io.py`, `pipeline/spx/frame.py`, `pipeline/spx/pairs.py`, `pipeline/spx/render.py`, `pipeline/spx/manifest.py`, `pipeline/spx/moving.py`
- `pipeline/build_field.py`, `pipeline/build_all.py`, `pipeline/build_dial.py` (packaging only), `pipeline/build_timeline.py`, `pipeline/find_mover.py`, `pipeline/export_injection_inputs.py`, `pipeline/fetch_*.py`, `pipeline/fields.yaml`, `pipeline/tests/`
- `poc/`, `data/` (git-ignored raw + meta), `web/public/data/`, `docs/DATA.md`, `docs/EXPERIMENTS.md` (data sections)
NEVER edit: `docs/CONTRACT.md`, `web/src/**`, `package.json`, `pipeline/spx/geometry.py`, `pipeline/spx/snr.py`, `poc/poc_b*` (Science owner). If one of them must change, STOP and say so.

## VERIFIED API FACTS (from IRSA tutorials, updated Mar 2026 — do not "improve" from memory)
- Collections (SIA2/TAP): `spherex_dr1` (Surveys 1–2, wide), `spherex_qr3` (Surveys 3–4, wide), `_deep` variants for the deep fields. QR2 is superseded and NOT searchable via SIA2. Search BOTH dr1 and qr3.
- Preferred search = TAP via astroquery (no 1-day SIA lag, can filter by detector):
```python
from astroquery.ipac.irsa import Irsa
q = f"""
SELECT 'https://irsa.ipac.caltech.edu/' || a.uri AS file_url, a.uri,
       p.time_bounds_lower, p.energy_bandpassname, p.planeid
FROM spherex.artifact a JOIN spherex.plane p ON a.planeid = p.planeid
WHERE 1 = CONTAINS(POINT('ICRS', {ra}, {dec}), p.poly)
  AND p.energy_bandpassname = 'SPHEREx-D2'
ORDER BY p.time_bounds_lower"""
tab = Irsa.query_tap(q).to_table()
```
  `time_bounds_lower` is MJD. Run `SELECT TOP 3 * FROM spherex.plane` / `spherex.artifact` once and use real column names (see `docs/DATA.md` after discovery).
- Fallback search = SIA2: `Irsa.query_sia(pos=(SkyCoord, radius), collection=['spherex_dr1','spherex_qr3'])`; columns `access_url`, `cloud_access` (JSON with aws bucket/key).
- Cutout = append to the file URL: `?center={ra},{dec}d&size={size_deg}` (size in degrees). Example from IRSA docs: `...level2_2026W21_2A_0001_2D1_spx_l2b-v27-2026-268.fits?center=337.8783221,-5.1891588&size=0.1`.
- MEF HDUs: 0 primary (`VERSION` = processing version), 1 `IMAGE` (MJy/sr, zodi NOT subtracted), 2 `FLAGS` (bitmask), 3 `VARIANCE`, 4 `ZODI`, 5 `EPSF` (or `PSF`), 6 `WCS-WAVE`. IMAGE header: `DETECTOR`, `OBSID`, `DATE`, `PSF_FWHM`.
- **Cutouts contain the full, unmodified ePSF table (~8 MB) even for a tiny cutout.** Budget download time accordingly; after download save a slim copy without EPSF.
- Spatial WCS: `WCS(hdul['IMAGE'].header)`. Wavelength at a pixel:
```python
sw = WCS(hdul['IMAGE'].header, fobj=hdul, key='W'); sw.sip = None   # SIP MUST be off
wl, bw = sw.pixel_to_world(x, y)                                     # Quantities -> .to(u.um)
```
  Cutout WCS-WAVE is already remapped to cutout pixels.
- FLAGS bit names live in the FLAGS header: `MSKNnnnn` = name, `MSKDnnnn` = description. **Most pixels carry the `SOURCE` bit — it is NOT a bad pixel.** Build the bad mask from an explicit list of bad-bit names read from the header, never `flags != 0`.
- Wavelength varies along the detector (LVF): bands D1 0.75–1.09, D2 1.10–1.62, D3 1.63–2.41, D4 2.42–3.82 (R≈35–41), D5 3.83–4.41 (R≈112), D6 4.42–5.00 µm (R≈128). Pixel 6.15″.
- Increase timeouts: `from astropy.utils.data import conf; conf.remote_timeout = 120`. Transient errors: TimeoutError, HTTPError, IncompleteRead, RemoteDisconnected → retry with backoff. Max 8 parallel workers against IRSA.
- Public cloud mirror (fallback): bucket `nasa-irsa-spherex` (us-east-1), path from SIA `cloud_access` JSON; `fits.open('s3://bucket/key', fsspec_kwargs={'anon': True})` (needs s3fs).

## Rules
- Never fabricate data. Anything synthetic/injected → `provenance.synthetic = true`. Fixtures never ship in the gallery.
- No discovery claims anywhere (code, comments, copy). Known objects only.
- Every frame record carries provenance: source_url, obs_id, mjd + UTC, detector, wavelength_um at target, processing version, collection, bad_pixel_fraction, downloaded_utc. A frame without it does not enter the product.
- Network calls only inside `pipeline/spx/io.py` (and `moving.py` for ephemerides). Everything downstream works offline from `data/`.
- Cache: a file already in `data/raw/` is never downloaded again. Second run of any build = zero downloads.
- Units in names/docstrings: `_deg`, `_au`, `_um`, `mjd`. Small functions, type hints, pytest for logic.
- New dependency → ask first. Allowed now: numpy, astropy, astroquery, pyvo, requests, reproject, Pillow, pyyaml, jsonschema, pandas, pytest, matplotlib, s3fs (fallback only).
- Finish every task with: what you built · how you tested (commands + output numbers) · what is NOT done · exact commands to run.
