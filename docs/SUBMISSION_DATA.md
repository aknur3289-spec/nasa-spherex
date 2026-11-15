# Project page data text

## NASA Data

We use NASA SPHEREx Level 2 spectral-image cutouts served by NASA/IPAC IRSA. The published gallery contains 93 real frames: 32 in `m101` (12 high-trust pairs), 31 in `nep` (10 high-, 2 medium-, and 6 low-trust pairs), and 30 in `ecl` (12 high- and 6 low-trust pairs). Their source URLs identify 64 frames from `spherex_dr1` and 29 from `spherex_qr3`. Observations run from 2025-05-03 to 2026-09-29 UTC; every published frame records processing version `7.0.5`, observation time, detector, wavelength, and source URL. The gallery's synthetic demo is excluded from all real-data counts. Data DOI: 10.26131/IRSA678 (DR1); 10.26131/IRSA662 (QR3).

## Space Agency Partner & Other Data

JPL Horizons geocentric ephemerides provide predicted positions for the known planets Neptune and Uranus at exposure times; Astropy handles astronomical coordinates, times, FITS, and WCS. Python libraries used in the pipeline and analysis are NumPy, Astropy, Astroquery, Requests, Pandas, Reproject, Pillow, PyYAML, JSON Schema (`jsonschema`), and Matplotlib; Pytest checks pipeline logic. PyVO is installed for VO work, while `s3fs` is reserved for the optional IRSA cloud fallback. The planet cutouts serve as validation inputs for the distance method, not as a discovery claim.

## Planet validation inputs

Neptune validation uses 103 unique exposures and 88 same-wavelength templates. Uranus validation uses 181 cutouts at JPL Horizons ephemeris positions, downloaded through Google Colab. They cover three quadrature windows: August 2025 (MJD 60911), February 2026 (MJD 61087), and August 2026 (MJD 61281). These planet inputs are separate from the published gallery.

## Blind moving-object test

Neptune's June and December 2025 SPHEREx exposures were searched without JPL Horizons. Each exposure was
differenced against a same-sky reference from another time (June 2025 frames ≥ 4 days apart for June;
June 2026 templates for December), new sources above 5σ were detected, and detections were linked into
tracks. Neptune was found in 64 of 74 differences and was the only track classed as a real mover; 8 other
tracks were rejected as static sources, optical ghosts or glare companions. A circular-orbit fit from the
June track to the December track gives 29.93 AU (bootstrap σ 0.02 AU) versus the Horizons heliocentric
distance 29.89 AU, used only for grading. Keeping the SPHEREx `OUTLIER`/`TRANSIENT` flags (which mark moving
sources) retains 10 detections that the standard mask removes. Injection–recovery on the control fields
gives 50 % completeness near 10× the pixel noise. The cutouts were downloaded around Neptune, so the search
area was chosen with prior knowledge. Code: `poc/blind_mover.py`, `poc/blind_mover_tests.py`; details:
`docs/BLIND_TEST.md`.
