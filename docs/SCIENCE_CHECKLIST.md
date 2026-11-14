# Strict science audit checklist

Audit date: 2026-11-14. Scope: read-only audit; no code, data, or existing documentation was changed. Only this checklist is new.

## Main result

1. **Status: PASS.** docs/EXPERIMENTS.md:129-154 identifies E4f's 265-pair median as HEADLINE and records command, JSON, and producing commit for all four runs: E4e `PYTHONPATH=pipeline:poc python poc/poc_b_astrometry.py`, astrometric_distance.json, dbbf7ef; E4f `PYTHONPATH=pipeline:poc python poc/poc_b_astrometry.py --all-local`, astrometric_distance_all.json, a3b038f; E4g `PYTHONPATH=pipeline:poc python poc/poc_b_astrometry.py --body uranus`, astrometric_distance_uranus.json, 14795fd; E4h `PYTHONPATH=pipeline:poc python poc/poc_b_astrometry.py --body neptune --epoch-a 2 --epoch-b 3`, astrometric_distance_neptune_w23.json, 48687de.

2. **Status: PASS.** docs/NUMBERS.md:3-12 establishes one headline and site/slides rounding; errors recomputed from unrounded JSON:
   - poc/out/astrometric_distance.json: measured 29.935715308957782 AU; JPL truth 29.88803609144112 AU; error +0.1595260972343264%.
   - poc/out/astrometric_distance_all.json: measured 29.95248812203051 AU; JPL truth 29.88803609144112 AU; error +0.21564491688982754%.

   Search command from the initial audit: rg -n -P '(?<![0-9.])(?:29\.94|29\.95|0\.16|0\.17|0\.2|0\.22)(?![0-9])' docs README* poc/README*. docs/NUMBERS.md:10 marks 29.94 as historical/superseded; headline is 29.95 AU, +0.2% for site/slides and +0.22% in docs. The 9-pair result is separately +0.16%; Uranus −0.54%; W2→W3 −0.06%. NUMBERS.md:12 specifies the one-pair dial minima 29.9/41.6 and distinguishes them from headline.

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

8. **Status: PASS.** poc/uncertainty.py and poc/out/uncertainty.json provide 10,000-resample bootstrap 68% median intervals and centroid-offset propagation for all-pairs Neptune, Uranus, and Neptune W2→W3. Headline bootstrap CI is [29.952488, 29.952488] AU (±0.00 AU to two decimals; degenerate due repeated grid-valued fits). Centroid RMS is 5.851954″; central finite-difference sensitivity is 2.641955″/AU; propagated sigma is 2.215009 AU (±2.22). docs/EXPERIMENTS.md and docs/NUMBERS.md report pair scatter separately (std 0.0182 AU; p16–p84 29.9325–29.9625 AU).

## Controls

9. **Status: PASS.** 77.8 and 0.43 are peak IMAGE surface-brightness values in MJy/sr, within 3 px of center at the same sky coordinate in June 2025 and June 2026, not integrated flux. docs/EXPERIMENTS.md:91-94 records rounded values; poc/README_pocb.md:18-24 gives 77.7839 and 0.4294 MJy/sr.

10. **Status: PASS.** Both cutouts sample RA=2.15087°, Dec=−0.5024° from poc/out/focus_neptune.json; poc/poc_b_dial.py:163-182 uses the fixed window-1 coordinate. Window-1 exposure 2025W25_2A_0500_1 points at s_ra=0.7780298782109514°, s_dec=−0.5669726635430189° (poc/coverage_neptune.csv); target pixel (43.3445,43.6041). Window-3 identity exposure 2026W25_2A_0645_1 D2 points at s_ra=1.2945988416126026°, s_dec=−2.589665559868902°; target pixel (43.9123,43.2920). Pointings differ; sampled sky coordinate is the same.

11. **Status: PASS (Gaia DR3 check only).** Gaia DR3 cone search at measured RA=2.151061989865566°, Dec=−0.5018771784909746°, radius 10 arcsec, table gaiadr3.gaia_source. Command: Gaia.cone_search_async(coord, radius=10*u.arcsec, table_name='gaiadr3.gaia_source', verbose=False); table=job.get_results(). Output: INFO: Query finished. [astroquery.utils.tap.core]; GAIA_SEARCH_OK 0. No Gaia DR3 source within 10 arcsec; this does not exclude other catalogs or uncatalogued sources.

## For the site

12. **Status: PASS.** docs/dial_table_neptune.csv:1 identifies ref 2025W25_2A_0500_1, target 2025W51_1A_0485_1, truth 29.89 AU. 251 rows span 20–45 AU by 0.1. At 29.9 AU (:102), model RA=359.624381°, Dec=−1.601139°, miss=83.1″; table minimum 29.9 AU / 83.1″. Parallax-only minimum 41.6 AU / 85.9″. Main 9-pair median 29.935715 AU, 0.035715 AU above nearest grid minimum. pipeline/make_dial_table.py:16-29 documents grid, target-time prediction, miss, minimum.

13. **Status: PASS.** poc/out/astrometric_residual.png is the miss-versus-distance plot; generated by poc/poc_b_astrometry.py:237-243 with English labels “Assumed heliocentric distance (AU)” and “Angular miss at epoch B (arcsec)”.

14. **Status: PASS.** docs/figures/detectability.png and .svg visibly include the requested footnote: “Planet Nine V = 21.9–22.7 from arXiv:2507.22297. Reflected-light estimate; methane absorption can make it fainter in some SPHEREx bands.” Regenerated using `python pipeline/make_slide_figures.py --detectability-only`; the new footer sits below the prior figure content. The exact text is present in both formats.

15. **Status: PASS.** docs/SCIENCE_SUMMARY.md:3-5 contains the three requested sentences: measured result/method, Horizons and Uranus validation plus parallax-only range, and assumptions/visibility/sensitivity limitation.

16. **Status: PASS.** docs/fixture_dial_neptune_synthetic.json:5-6 labels “SYNTHETIC fixture” and “Synthetic images”; provenance has synthetic: true near line 2898. docs/DECISIONS.md:6 says synthetic assets are labelled DEMO DATA.

## Limitations

17. **Status: PASS.** docs/EXPERIMENTS.md:39 says Neptune/Uranus are bright and probably saturated and “they prove geometry, not sensitivity.”

18. **Status: PASS.** docs/SCIENCE_SUMMARY.md:11 states the circular ecliptic-plane assumption and gives a 20° inclined circular-orbit example over 178.253 days: mismatch 1,340.38″; fitting the inclined synthetic position with the ecliptic model returns 29.1523 AU for a 30 AU input, bias −0.8477 AU (−2.83%). This orientation-specific illustration is not presented as universal.

19. **Status: PASS (empirical bound; chromatic-only component not isolated).** docs/SCIENCE_SUMMARY.md:12 records dial-pair wavelengths 0.968 µm June and 1.259 µm December, and all-pairs measured-vs-Horizons offsets: min/median/max 0.141/2.700/27.418″ = 0.023/0.439/4.458 px. At 2.642″/AU local sensitivity, maximum-offset distance scale is 10.38 AU. This bounds total empirical positional residual, not a wavelength-only contribution.

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
| 1 | PASS | EXPERIMENTS.md:129-154; commands and four hashes | — |
| 2 | PASS | NUMBERS.md:3-12; full-precision JSON errors | — |
| 3 | PASS | poc_b_astrometry.py:183-210 | — |
| 4 | PASS | combinations fields; medians above | — |
| 5 | PASS | geometry.py:66-91; callers above | — |
| 6 | PASS | poc_b_astrometry.py:130-148,196-201 | — |
| 7 | PASS | Three output JSON files; table above | — |
| 8 | PASS | uncertainty.py/.json; EXPERIMENTS and NUMBERS uncertainty row | — |
| 9 | PASS | EXPERIMENTS.md:91-94; README values above | — |
| 10 | PASS | dial identity code, coverage and pixels above | — |
| 11 | PASS | Gaia DR3 10″ query returned 0 rows | — |
| 12 | PASS | dial_table_neptune.csv; builder lines 16-29 | — |
| 13 | PASS | poc/out/astrometric_residual.png | — |
| 14 | PASS | detectability.png/.svg footnote; make_slide_figures.py | — |
| 15 | PASS | SCIENCE_SUMMARY.md:3-5 | — |
| 16 | PASS | synthetic fixture lines 5-6 and provenance | — |
| 17 | PASS | EXPERIMENTS.md:39 | — |
| 18 | PASS | SCIENCE_SUMMARY.md:11; inclined-orbit calculation | — |
| 19 | PASS | SCIENCE_SUMMARY.md:12; wavelengths and empirical bound | — |
| 20 | PASS | EXPERIMENTS.md:123-127 | — |
| 21 | PASS | Clean clone: 12 passed in 10.45s | — |
| 22 | PASS | merge-tree exit 0; refs above | — |
| 23 | PASS | grep command and hits above | — |
