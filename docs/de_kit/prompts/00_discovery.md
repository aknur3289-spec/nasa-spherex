# P00 — Discovery: prove access, dump real schemas (run FIRST, ~20 min)
Tool: Claude Code (it runs, reads errors, retries). Branch: `data/discovery`.

---
Read AGENTS.md first. You are the data engineer's agent. Goal: in 20 minutes prove we can reach SPHEREx data from this machine and record the REAL column names, headers and flag bits, so that every later prompt works from facts, not guesses.

FILES (create only these)
- `poc/discover.py`
- `docs/DATA.md` (section "Discovery results")
- `data/meta/discovery/` (outputs, git-ignored except the .txt/.json summaries)

STEPS
1. `pip install numpy astropy astroquery pyvo requests reproject Pillow pyyaml jsonschema pandas pytest matplotlib` (report versions).
2. TAP: run `SELECT TOP 3 * FROM spherex.plane` and `SELECT TOP 3 * FROM spherex.artifact` via `Irsa.query_tap`. Save column names + one example row to `data/meta/discovery/tap_columns.json`.
3. Run the verified TAP query from AGENTS.md for M101 (ra=210.80227, dec=54.34895) WITHOUT the detector filter, but add `p.energy_bandpassname` to the output. Report: total rows, rows per bandpass, min/max MJD, and whether the uri prefix tells us dr1 vs qr3 (e.g. `/spherex/dr1/` vs `/spherex/qr3/`). Save to `data/meta/discovery/m101_tap.csv`.
4. Also run SIA2 for the same point (`collection=['spherex_dr1','spherex_qr3']`, radius 1 arcsec). Report row count and `colnames`. Save colnames.
5. Download ONE cutout (size 0.1667 deg = 10 arcmin) of the earliest D2 row. Time it, report file size in MB. Print `hdul.info()`, and save to `data/meta/discovery/header_sample.txt`: primary header, IMAGE header, FLAGS header.
6. From the FLAGS header print a table bit | MSKN name | MSKD description → `data/meta/discovery/flag_bits.json`. Report the fraction of pixels having each bit set in this cutout.
7. Compute wavelength at the target pixel with the spectral WCS (key='W', sip=None). Check that the IMAGE shape is ~98×98 px (10′ / 6.15″). Check whether a time keyword exists in the IMAGE header (MJD-OBS / DATE-OBS / etc.) and compare with `time_bounds_lower`.
8. Write a 15-line summary into `docs/DATA.md`: working search method, real column names, file size per cutout, seconds per cutout, flag bit table, proposed BAD_BITS list (everything that means unusable pixel: e.g. non-functional, saturated, transient/cosmic ray, hot/cold, missing — use names exactly as in header; EXCLUDE `SOURCE`), and anything surprising.

IF TAP FAILS: try SIA2; if both fail, try the cloud mirror via `cloud_access`; report exact errors. Do not spend more than 10 minutes on any one method.

DONE WHEN: one real cutout is on disk, its wavelength at the target is printed, and docs/DATA.md lists the real column names and the BAD_BITS proposal.
