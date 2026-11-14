# Project page data text

## NASA Data

We use NASA SPHEREx Level 2 spectral-image cutouts served by NASA/IPAC IRSA. The published gallery contains 93 real frames: 32 around M101, 31 near the north ecliptic pole, and 30 in an ecliptic test field. Their source URLs identify 64 frames from `spherex_dr1` and 29 from `spherex_qr3`. Observations run from 2025-05-03 to 2026-09-29 UTC; every published frame records processing version `7.0.5`, observation time, detector, wavelength, and source URL. Our local validation metadata separately records 103 ready Neptune cutouts and 2 ready Uranus cutouts; these are not gallery frames. The gallery's synthetic demo is excluded from all real-data counts. Data DOI: [DOI from IRSA release page].

## Space Agency Partner & Other Data

JPL Horizons geocentric ephemerides provide predicted positions for the known planets Neptune and Uranus at exposure times; Astropy handles astronomical coordinates, times, FITS, and WCS. Python libraries used in the pipeline and analysis are NumPy, Astropy, Astroquery, Requests, Pandas, Reproject, Pillow, PyYAML, JSON Schema (`jsonschema`), and Matplotlib; Pytest checks pipeline logic. PyVO is installed for VO work, while `s3fs` is reserved for the optional IRSA cloud fallback. The planet cutouts serve as validation inputs for the distance method, not as a discovery claim.

## Count check before submission

The requested figures of **162 Neptune** and **181 Uranus** cutouts are not verified by this checkout. Current `data/meta/neptune/epochs.csv` has 103 ready rows, and `data/meta/uranus/epochs.csv` has 2. Replace the validation counts above only after the additional cutouts and their metadata are present and checked.
