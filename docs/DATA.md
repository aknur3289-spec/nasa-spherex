# SPHEREx data

## Discovery results

- Run: 2026-11-14 07:04 UTC, branch `data/discovery`.
- Working search method from this machine: **none verified**; outbound HTTPS connection timed out.
- TAP endpoint (`irsa.ipac.caltech.edu:443`): `TimeoutError: timed out` before a query could run.
- SIA2 uses the same IRSA host; its HTTPS connection also timed out.
- Public cloud mirror (`nasa-irsa-spherex.s3.amazonaws.com:443`): `TimeoutError: timed out`.
- Independent `curl -4 -I --max-time 12` checks to IRSA, Google, and S3 all timed out, indicating a machine/network access problem.
- Real `spherex.plane` and `spherex.artifact` column names: **not obtained**.
- M101 TAP rows, bandpass counts, MJD range, and URI collection prefixes: **not obtained**.
- SIA2 row count and column names: **not obtained**.
- D2 cutout size, transfer time, HDU headers, image shape, and target wavelength: **not obtained**; no FITS file was downloaded.
- Flag bit table and per-bit fractions: **not obtained**. `SOURCE` must be excluded from a bad-pixel mask.
- Proposed `BAD_BITS`: **pending real FLAGS header**; selecting names now would be a guess.
- Machine-readable connection failures: `data/meta/discovery/results.json` (git-ignored).
- Rerun when HTTPS access works: `python3 -u poc/discover.py` from the repo root.

Installed versions: numpy 2.3.5, astropy 8.0.2, astroquery 0.4.11, pyvo 1.10.0, requests 2.32.4, reproject 0.21.0, Pillow 12.3.0, pyyaml 6.0.2, jsonschema 4.25.0, pandas 3.0.5, pytest 9.1.1, matplotlib 3.10.5.
