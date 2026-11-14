# Strict science audit checklist

Audit date: 2026-11-14. Scope: read-only audit; no code, data, or existing documentation was changed. Only this checklist is new.

## Main result

1. **Status: PARTIAL.** docs/EXPERIMENTS.md:129-137 records the real-image Neptune 9-pair result and script path, and gives commit dbbf7ef, but omits the run command. docs/EXPERIMENTS.md:143-149 records the 265-pair result without command or commit. Commands: PYTHONPATH=pipeline:poc python poc/poc_b_astrometry.py (9-pair); PYTHONPATH=pipeline:poc python poc/poc_b_astrometry.py --all-local (all-local, commit a3b038f). **Fix:** add exact command and commit beside each result and distinguish the 9-pair and 265-pair runs.

2. **Status: PARTIAL.** Recomputed from unrounded JSON:
   - poc/out/astrometric_distance.json: measured 29.935715308957782 AU; JPL truth 29.88803609144112 AU; error +0.1595260972343264%.
   - poc/out/astrometric_distance_all.json: measured 29.95248812203051 AU; JPL truth 29.88803609144112 AU; error +0.21564491688982754%.

   Search command: rg -n -P '(?<![0-9.])(?:29\.94|29\.95|0\.16|0\.17|0\.2|0\.22)(?![0-9])' docs README* poc/README*. Hits: docs/EXPERIMENTS.md:134 (29.94, 0.16); :140 (0.2); :147 (29.95, 0.22); docs/NUMBERS.md:5 (29.94); :7 (0.2, 0.16, 0.17, 29.94); :16 (29.95, 0.22); docs/limits.json:374 (0.17, unrelated albedo). No matches in README or poc/README_pocb.md. Values 29.94/0.16 refer to 9 pairs; 29.95/0.22 refer to 265 pairs. docs/NUMBERS.md:7 mixes rounded display values with exact 9-pair error and shows rounded arithmetic as 0.17%. **Fix:** document each dataset separately with errors derived from unrounded values.

3. **Status: PASS.** Truth is heliocentric r_au averaged over the two window ephemeris rows, not geocentric delta_au or an individual exposure-time value. poc/poc_b_astrometry.py:183-187 collects window r_au and computes the mean; :209-210 names it truth_r_au and identifies the mean of window-1/window-2 rows. All-local/body paths also average window r_au (:266, :413).

4. **Status: PASS.** Each record in poc/out/astrometric_distance.json combinations stores circular and static fits for the same exposure pair. Dial pair 2025W25_2A_0500_1 → 2025W51_1A_0485_1 static fit: 41.60465349202536 AU. 9-pair static median: 41.60465349202536 AU. 265-pair static median: 40.58514628657164 AU (astrometric_distance_all.json).

## Method honesty

5. **Status: PASS.** pipeline/spx/geometry.py:66-91 shows predict_radec uses initial sky position, initial time, trial distance, requested times, and orbit model; no target Horizons ephemeris. poc/poc_b_astrometry.py:196-201 calls fit_distance with measured A/B coordinates. pipeline/make_dial_table.py:13-20 reads measured A coordinates and calls predict_radec(ra0, dec0, t0, d, t1, ...).

6. **Status: PASS.** poc/poc_b_astrometry.py:130-145 estimates background, finds the brightest pixel, computes a flux-weighted centroid, and converts it using wcs.pixel_to_world. Lines 196-201 pass measured_ra_deg/measured_dec_deg to the fit. Ephemeris positions center the measurement section, not the fitted target coordinates.

7. **Status: PASS.** Pair counts and empirical scatter (population standard deviation, ddof=0):

   | Dataset | Exposures A × B | Pairs | Circular median; p16–p84; std (AU) | Static median; p16–p84; std (AU) |
   |---|---:|---:|---|---|
   | Neptune all-pairs | 53 × 5 | 265 | 29.952488; 29.932483–29.962491; 0.018214 | 40.585146; 40.145036–41.105276; 0.483991 |
   | Uranus | 3 × 3 | 9 | 19.391630; 19.346413–19.391630; 0.021315 | 29.313321; 28.981528–29.638118; 0.345108 |
   | Neptune W2→W3 | 3 × 3 | 9 | 29.865913; identical p16/p84; ~0 | 22.994557; 22.917438–23.102169; 0.121609 |

   Sources: poc/out/astrometric_distance_all.json, astrometric_distance_uranus.json, astrometric_distance_neptune_w23.json; exposures, n_combinations, median_d_fit_au, p16_p84_au, std_au fields.

8. **Status: PARTIAL.** Outputs report pair-to-pair spread, but no propagated centroid-error uncertainty or bootstrap confidence interval on the median. Pair spread is not formal uncertainty on inferred distance. **Fix:** add measurement-error/bootstrap uncertainty and label pair scatter separately.

## Controls

9. **Status: PASS.** 77.8 and 0.43 are peak IMAGE surface-brightness values in MJy/sr, within 3 px of center at the same sky coordinate in June 2025 and June 2026, not integrated flux. docs/EXPERIMENTS.md:91-94 records rounded values; poc/README_pocb.md:18-24 gives 77.7839 and 0.4294 MJy/sr.

10. **Status: PASS.** Both cutouts sample RA=2.15087°, Dec=−0.5024° from poc/out/focus_neptune.json; poc/poc_b_dial.py:163-182 uses the fixed window-1 coordinate. Window-1 exposure 2025W25_2A_0500_1 points at s_ra=0.7780298782109514°, s_dec=−0.5669726635430189° (poc/coverage_neptune.csv); target pixel (43.3445,43.6041). Window-3 identity exposure 2026W25_2A_0645_1 D2 points at s_ra=1.2945988416126026°, s_dec=−2.589665559868902°; target pixel (43.9123,43.2920). Pointings differ; sampled sky coordinate is the same.

11. **Status: PASS (Gaia DR3 check only).** Gaia DR3 cone search at measured RA=2.151061989865566°, Dec=−0.5018771784909746°, radius 10 arcsec, table gaiadr3.gaia_source. Command: Gaia.cone_search_async(coord, radius=10*u.arcsec, table_name='gaiadr3.gaia_source', verbose=False); table=job.get_results(). Output: INFO: Query finished. [astroquery.utils.tap.core]; GAIA_SEARCH_OK 0. No Gaia DR3 source within 10 arcsec; this does not exclude other catalogs or uncatalogued sources.

## For the site

12. **Status: PASS.** docs/dial_table_neptune.csv:1 identifies ref 2025W25_2A_0500_1, target 2025W51_1A_0485_1, truth 29.89 AU. 251 rows span 20–45 AU by 0.1. At 29.9 AU (:102), model RA=359.624381°, Dec=−1.601139°, miss=83.1″; table minimum 29.9 AU / 83.1″. Parallax-only minimum 41.6 AU / 85.9″. Main 9-pair median 29.935715 AU, 0.035715 AU above nearest grid minimum. pipeline/make_dial_table.py:16-29 documents grid, target-time prediction, miss, minimum.

13. **Status: PASS.** poc/out/astrometric_residual.png is the miss-versus-distance plot; generated by poc/poc_b_astrometry.py:237-243 with English labels “Assumed heliocentric distance (AU)” and “Angular miss at epoch B (arcsec)”.

14. **Status: PARTIAL.** Source/caveat occur in docs/limits.json:2-7,523 (arXiv 2507.22297; methane/phase caveats), docs/limits_zones.json:491-497, docs/EXPERIMENTS.md:53-54, and web/src/viewer/SciencePanels.tsx:147. Rendered docs/figures/detectability.svg has no citation/caveat text (search for 2507.22297, methane, reflected found none). **Fix:** add a visible source and methane/reflected-light caveat to the figure or adjacent caption.

15. **Status: PARTIAL.** docs/EXPERIMENTS.md:129-136 explains centroiding, Horizons agreement, and circular-orbit residual, but not as three explicit sentences covering what is measured, validation, and what the method cannot do. **Fix:** add those three English sentences in a discoverable project/site file.

16. **Status: PASS.** docs/fixture_dial_neptune_synthetic.json:5-6 labels “SYNTHETIC fixture” and “Synthetic images”; provenance has synthetic: true near line 2898. docs/DECISIONS.md:6 says synthetic assets are labelled DEMO DATA.

## Limitations

17. **Status: PASS.** docs/EXPERIMENTS.md:39 says Neptune/Uranus are bright and probably saturated and “they prove geometry, not sensitivity.”

18. **Status: PARTIAL.** Circular prograde orbit about ecliptic pole assumption appears in docs/EXPERIMENTS.md:9 and pipeline/spx/geometry.py:3-5. Audited docs do not say inclined orbits yield larger error. **Fix:** state that the circular ecliptic-plane approximation can increase error for inclined orbits.

19. **Status: PARTIAL.** WCS-WAVE at target position: June ref 2025W25_2A_0500_1 D1 = 0.9680158231710037 µm; December target 2025W51_1A_0485_1 D2 = 1.2593303817343426 µm (30.09% difference relative to first wavelength). Docs do not state the pairwise wavelength difference or assess centroiding impact. Wavelength-dependent PSF/centroid systematics may affect it; impact is unquantified. **Fix:** record both wavelengths and quantify or bound the chromatic centroid systematic.

20. **Status: PASS.** docs/EXPERIMENTS.md:123-127 says the real full-range grid was infeasible because most steps lacked matched templates/stars/window-2 coverage and predicted positions span degrees; full-range dial remains synthetic, real validation astrometric.

## Handoff

21. **Status: PASS.** Fresh clone command: source ~/nasa-spherex/.venv/bin/activate && git clone ~/nasa-spherex /tmp/audit_clone -b feat/science && cd /tmp/audit_clone && source ~/nasa-spherex/.venv/bin/activate && python -m pytest -q. Output: ............ [100%]; 12 passed in 10.45s. Generated SVG diff restored in temporary clone; audited worktree untouched.

22. **Status: PASS.** Fetched origin in /tmp/audit_clone and ran git merge-tree --write-tree origin/main feat/science. Output tree db6b3e1709f7ef8c92b28b88a69cabcda034d58a, exit 0, no conflict output. origin/main=25ba30e049e52a7d2b48dc25c7064301d0b60043; feat/science=6c710f62b500c5aad38a61056817d352b26c6a9e.

23. **Status: PASS (search completed).** Command: grep -rniw -E 'discovered|detected planet|candidate' docs README.md site web 2>&1 || true. site/ missing (grep: site: No such file or directory). No discovered/exact “detected planet” hits and no hits in docs/ or README. web hits:
   - web/src/viewer/SciencePanels.tsx:65,82,83.
   - web/src/survey/App.tsx:343,344,347,457,474,546,549,561,563,564,569,598,607,608,635,638,676,677,695,698,715,728,755,781,809,851,940,948. Text includes “High-priority candidate” (:561), “SPHEREx moving source candidate · First detected 2025-04-18” (:564), “Strong candidate” (:638), “Compare candidate” (:755), “CANDIDATE ANALYSIS” (:781), “From raw light to candidate” (:851).
   - web/src/survey/index.css:523,672,677,691,692,697,703,710,713,718,721,1346,1483,1613,1909 (candidate selectors/comments).

## Summary table

| Item | Status | Evidence | Fix |
|---:|---|---|---|
| 1 | PARTIAL | EXPERIMENTS.md:129-149; command/hash gaps | Add command and commit per result |
| 2 | PARTIAL | JSON full-precision values above; NUMBERS.md:7 | Separate sets and calculate unrounded |
| 3 | PASS | poc_b_astrometry.py:183-210 | — |
| 4 | PASS | combinations fields; medians above | — |
| 5 | PASS | geometry.py:66-91; callers above | — |
| 6 | PASS | poc_b_astrometry.py:130-148,196-201 | — |
| 7 | PASS | Three output JSON files; table above | — |
| 8 | PARTIAL | Pair spread only | Add formal uncertainty estimate |
| 9 | PASS | EXPERIMENTS.md:91-94; README values above | — |
| 10 | PASS | dial identity code, coverage and pixels above | — |
| 11 | PASS | Gaia DR3 10″ query returned 0 rows | — |
| 12 | PASS | dial_table_neptune.csv; builder lines 16-29 | — |
| 13 | PASS | poc/out/astrometric_residual.png | — |
| 14 | PARTIAL | JSON/text cite; SVG omits caveat | Add visible figure source/caveat |
| 15 | PARTIAL | EXPERIMENTS.md:129-136 | Add three explicit sentences |
| 16 | PASS | synthetic fixture lines 5-6 and provenance | — |
| 17 | PASS | EXPERIMENTS.md:39 | — |
| 18 | PARTIAL | Assumption stated; inclination caveat absent | Add inclined-orbit limitation |
| 19 | PARTIAL | Pair wavelengths above; impact unquantified | Record and bound chromatic effect |
| 20 | PASS | EXPERIMENTS.md:123-127 | — |
| 21 | PASS | Clean clone: 12 passed in 10.45s | — |
| 22 | PASS | merge-tree exit 0; refs above | — |
| 23 | PASS | grep command and hits above | — |
