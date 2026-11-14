# SPHEREx data

## Discovery results

- Live run: 2026-11-14 08:44 UTC; TAP and SIA2 both worked from this machine.
- M101 position: RA 210.80227°, Dec 54.34895°; SIA2 radius 1 arcsec; cutout size 0.1667°.
- TAP returned 376 rows: D1 52, D2 84, D3 53, D4 53, D5 83, D6 51.
- TAP MJD range: 60804.148555–61215.138195; URI prefixes identify `/spherex/dr1/` (246) and `/spherex/qr3/` (130).
- SIA2 returned 376 rows. Its real column names are in `data/meta/discovery/sia_columns.json`.
- The earliest D2 row is in DR1; its cutout is `data/raw/m101_earliest_d2_cutout.fits`.
- First download took 26.919 s and produced 4.104 MB (decimal); later runs use the cached file.
- HDUs: PRIMARY, IMAGE, FLAGS, VARIANCE, ZODI, EPSF, WCS-WAVE; the EPSF data span is 3.862 MB.
- IMAGE is 98×98 pixels, matching 10 arcmin / 6.15 arcsec per pixel (~98 pixels).
- Target pixel is (48.921, 48.498); spectral WCS with SIP disabled gives **1.506421 µm**.
- IMAGE `MJD-OBS` is 60805.711547928; TAP `time_bounds_lower` is 60805.711548 (difference −0.006 s, from catalog rounding).
- IMAGE `DATE-OBS` is 2025-05-10T17:04:37.741 UTC; `DATE` is the later HDU creation time, not the observation time.
- FLAGS defines 22 named planes. `SOURCE` covers 92.201% of this cutout and is **not** a bad pixel.
- Proposed conservative `BAD_BITS`: `TRANSIENT`, `OVERFLOW`, `SUR_ERROR`, `NONFUNC`, `DICHROIC`, `MISSING_DATA`, `HOT`, `COLD`, `PHANMISS`, `NONLINEAR`, `PERSIST`, `OUTLIER`, `CROSSTALK`, `GHOST`, `GHOST_FPA`, `GHOST_EXT`, `STREAK`, `BLOOM`, `SNOWBALL`, `HALO`. Review this policy with Science before product use.
- The 4.104 MB cutout is smaller than the earlier ~8 MB EPSF estimate; it still carries the full EPSF table.

### Real TAP column names

- `spherex.plane`: `obsid`, `planeid`, `productid`, `creatorid`, `metarelease`, `datarelease`, `calibrationlevel`, `dataproducttype`, `quality_flag`, `metrics_sourcenumberdensity`, `metrics_background`, `metrics_backgroundstddev`, `metrics_fluxdensitylimit`, `metrics_maglimit`, `position_dimension_naxis1`, `position_dimension_naxis2`, `position_resolution`, `position_samplesize`, `position_timedependent`, `energy_bounds_lower`, `energy_bounds_upper`, `energy_bounds_samples`, `energy_emband`, `energy_dimension`, `energy_resolvingpower`, `energy_samplesize`, `energy_bandpassname`, `energy_transition_species`, `energy_transition_transition`, `energy_restwav`, `time_bounds_lower`, `time_bounds_upper`, `time_bounds_samples`, `time_dimension`, `time_resolution`, `time_samplesize`, `time_exposure`, `polarization_states`, `polarization_dimension`, `provenance_name`, `provenance_reference`, `provenance_version`, `provenance_project`, `provenance_producer`, `provenance_runid`, `provenance_lastexecuted`, `provenance_keywords`, `ipac_gid`, `mission_id`, `poly`, `pt`, `ipac_pub_date`, `lastmodified`, `obs_publisher_did`.
- `spherex.artifact`: `planeid`, `artifactid`, `uri`, `producttype`, `releasetype`, `contenttype`, `contentlength`, `contentchecksum`, `ipac_gid`, `mission_id`, `ipac_pub_date`, `lastmodified`.
- Example rows are in `data/meta/discovery/tap_columns.json`; all 376 M101 TAP rows are in `data/meta/discovery/m101_tap.csv` (local, git-ignored).

### FLAGS bit planes in the D2 cutout

| Bit | MSKN name | MSKD description | Pixels set |
| ---: | --- | --- | ---: |
| 0 | TRANSIENT | Transient detected during SUR | 0.187% |
| 1 | OVERFLOW | Overflow detected during SUR | 0% |
| 2 | SUR_ERROR | Error in onboard processing | 0.146% |
| 6 | NONFUNC | Permanently unusable | 0.208% |
| 7 | DICHROIC | Low efficiency due to dichroic | 0% |
| 9 | MISSING_DATA | Onboard data lost | 0% |
| 10 | HOT | Hot pixel | 0% |
| 11 | COLD | Anomalously low signal | 0% |
| 12 | FULLSAMPLE | Pixel full sample history is available | 0% |
| 14 | PHANMISS | Phantom correction was not applied | 0% |
| 15 | NONLINEAR | Nonlinearity correction cannot be applied reliably | 0% |
| 17 | PERSIST | Persistent charge above threshold | 0.323% |
| 19 | OUTLIER | Pixel flagged by Detect Outliers | 0.187% |
| 20 | CROSSTALK | Pixel affected by crosstalk | 0% |
| 21 | SOURCE | Pixel mapped to a known source | 92.201% |
| 22 | GHOST | Affected by a bright source inside the exposure | 0% |
| 23 | GHOST_FPA | Affected by a bright source on another detector | 0% |
| 24 | GHOST_EXT | Pixel affected by a bright source outside FOV | 0% |
| 25 | STREAK | Pixel affected by a streak | 0% |
| 26 | BLOOM | Pixel part of a bloom artifact | 0% |
| 27 | SNOWBALL | Pixel part of a snowball artifact | 0% |
| 28 | HALO | Pixel part of a transient halo | 0.312% |

Full precision fractions and descriptions are in `data/meta/discovery/flag_bits.json`; FITS headers are in `data/meta/discovery/header_sample.txt`.

Installed versions: numpy 2.3.5, astropy 8.0.2, astroquery 0.4.11, pyvo 1.10.0, requests 2.32.4, reproject 0.21.0, Pillow 12.3.0, pyyaml 6.0.2, jsonschema 4.25.0, pandas 3.0.5, pytest 9.1.1, matplotlib 3.10.5.

Run again from the repository root: `python3 -u poc/discover.py`.

## Neptune Distance Dial offline packaging check — 2026-11-14

`python3 pipeline/build_dial.py --id neptune-2025 --target neptune --pass-a 2 --pass-b 3 --steps 48 --dmin 15 --dmax 1000` used only local FITS files. Pass A is December 2025. The selected reference is `2025W50_1A_0310_4`, detector 3, MJD 61018.329797361, with the lowest recorded central bad fraction. The Horizons truth matched at that exposure is heliocentric `r_au = 29.88539078335`; geocentric `delta_au = 29.6671831880975` is recorded separately.

The local pass B science inventory is empty. Twenty-five detector-3 June 2026 template cutouts are available, but all are centered near the December sky position. None contains the circular-orbit prediction at any of the 48 requested distances with the 20-pixel search margin. The detailed skip ledger is `data/meta/neptune/dial_summary.json` (local data, outside Git). There is no measured peak or percentage error. No `field.json` or PNGs were published because contract v1.1 requires at least one covered step, and the 20% peak gate cannot be evaluated. There are no local `data/raw/neptune-blank` cutouts, so no negative-control field was attempted.

The offline script loads Science's unchanged `_variance_snr` function from `poc/poc_b_dial_v2.py` if a covered cutout becomes available. Its current single-frame score would be diagnostic only; a matched-sky subtraction and Science signoff are still needed before publishing a dial field. This check cannot reproduce the earlier PoC B peak because its pass B sections along the distance track are not present in the specified local inventory.

## Neptune dial full-frame staging — 2026-11-14

`python3 pipeline/build_dial.py --neptune-field` uses the Science pair `2025W25_2A_0500_1` D1 and `2025W51_1A_0485_1` D2. It reads 10 arcmin sections from the full December L2 product through the public S3 mirror and caches each section in `data/raw/neptune-dial/`. The June 0.5 degree reference cutout is cached there too. The grid is `dial_grid(20, 45, step_px=15)`. Per-step SNR is the highest valid pixel `(image - median) / MAD noise` within 20 pixels; offset is that pixel's distance from the stamp centre. The report is `data/meta/neptune-dial/report.json`. A successful Science gate stages PNGs and `field.json` in that same ignored metadata directory; it does not publish to `web/public/data` while the Frontend validator is incompatible.

### Proposed v1.1 dial additions for Frontend agreement

The Python schema adds optional frame fields `collection` and `downloaded_utc`, and optional dial fields `ref_obs_id`, `target_obs_id`, `ref_detector`, `target_detector`, `truth_au`, `measured_au`, `measured_uncertainty_au`, and `note`. A step outside the full detector or within five arcmin of its edge has `outside_frame: true` and `frame`, `snr`, and `offset_px` set to `null`. Covered steps retain numeric SNR and offset and an existing frame ID. The Python semantic validator enforces this pairing. `web/src/data/validation.ts` and `web/src/contract.ts` currently require non-null step measurements, so Frontend must agree to and implement this additive shape before the staged dial is published. `docs/CONTRACT.md` is owned by Frontend and remains unchanged.

### Measured result and publication gate

The full-frame run evaluated 135 grid steps: 104 covered, 31 outside the detector margin. The smallest raw-image offset is 0.5 px at 36.79054 AU, 6.89565 AU above the ref-epoch JPL geocentric truth 29.89489 AU. This is not near the Science single-pair astrometric minimum of 29.9 AU and ~13.5 px in `docs/dial_table_neptune.csv`. The gate failed. No `neptune-dial` field or PNG was written to `web/public/data`; the detailed local report is `data/meta/neptune-dial/report.json`.

| Our grid d (AU) | Raw-image offset (px) | Nearest Science d (AU) | Science model miss (px) |
| ---: | ---: | ---: | ---: |
| 36.23960 | 18.58 | 36.2 | 232.34 |
| 36.51299 | 9.01 | 36.5 | 241.75 |
| 36.79054 | 0.50 | 36.8 | 251.04 |
| 37.07234 | 9.01 | 37.1 | 260.19 |
| 37.35849 | 17.01 | 37.4 | 269.23 |

The Science column is the predicted position's miss relative to known Neptune astrometry; our offset is the brightest pixel within a 20 px search circle. A near-centre unrelated source can therefore create a false minimum in the raw-image score. The negative-control field was not attempted after this failure.
