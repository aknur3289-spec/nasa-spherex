# EXPERIMENTS.md — scientific log (owner: Participant 1)

Every number shown in the UI or on slides must come from this file.

## E1. Geometry, no SPHEREx data (DONE, reproducible)
`python pipeline/validate_geometry.py` → `docs/validation_geometry.json`

Two true positions ~182.6 d apart, near quadrature (elongation ≈ 90°), blind distance fit.
Model: parallax + circular prograde orbit about the ecliptic pole (`spx/geometry.py`).

| Body | d true, AU | d fit, AU | err % | residual ″ | parallax-only fit | err % |
|---|---|---|---|---|---|---|
| Neptune | 29.89 | 29.88 | −0.0 | 79.5 (≈13 px) | 23.21 | −22.3 |
| Uranus | 19.48 | 19.49 | +0.1 | 97.9 | 14.37 | −26.3 |
| Saturn | 9.52 | 9.48 | −0.4 | 316 | 6.26 | −34.3 |

Conclusion: H2 geometry holds; the simple "shift = 2/d" model is 20–35 % off, so the orbit term is required.
Matches the plan's numbers (Neptune 29.8, 23.2 without orbit).

## E2. Focus curve on SYNTHETIC images (DONE — plumbing only, not evidence)
`python pipeline/make_synthetic_dial.py` → `docs/fixture_dial_neptune_synthetic.json` (synthetic: true)

| Case | Peak, AU | Peak / median | Verdict |
|---|---|---|---|
| Neptune, circular model | 29.91 (truth 29.89) | 226 | PASS |
| Neptune, parallax-only model | 42.5 | — | wrong, as expected |
| Empty sky 1° away | no peak (1.5) | 1.5 | PASS |

Lessons that apply to real data:
1. Grid must be uniform in 1/d (`dial_grid`): uniform-in-d grids jump ~170 px per step near 30 AU and miss Neptune.
2. Measure on a difference stamp (epoch t1 minus another epoch at the same sky position). On raw stamps,
   field stars inside the 20 px window make false peaks and the empty-sky control fails.

## E3. PoC A — Honest Blink pairs on real SPHEREx (TODO)
Fields: M101 (210.80227, 54.34895) + 2 more. Success: ≥3 pairs with Δλ/λ < 2 % and Δt > 150 d in 2 of 3 fields.

## E4. PoC B — Neptune on real SPHEREx (TODO)
Success: |err| ≤ 15 %, peak ≥ 3× median, empty-sky control has no peak. Positive control: Uranus.
Caveat for the pitch: Neptune/Uranus are bright and probably saturated — they prove geometry, not sensitivity.

## E5. Detectability (DONE, order of magnitude)
`cd docs && python ../pipeline/spx/detectability.py` → `docs/limits.json`

Single-frame limit AB 18.4 (verify in Explanatory Supplement); stack gain 1.25·log10 N.

| Body | max d, 1 frame | 100 frames | 300 frames |
|---|---|---|---|
| Neptune-size (p 0.41) | 338 AU | 601 AU | 690 AU |
| Planet Nine 10 M⊕ (~3 R⊕, p 0.4) | 296 | 525 | 602 |
| Planet Nine 5 M⊕ (~2 R⊕, p 0.4) | 241 | 429 | 492 |
| Earth-size | 168 | 298 | 341 |

Caveats: V used as proxy for near-IR AB; methane absorption ignored → real limits are worse.
Literature brightness for nominal Planet Nine: V ≈ 21.9–22.7 (arXiv 2507.22297) — fainter than the single-frame limit.

## E2b. Dial builder, synthetic, contract-valid (DONE)
`python pipeline/build_dial.py --provider synthetic --out out` (branch feat/sci-dial, commit 75a5fed)
Passes docs/CONTRACT.md (Python contract_check + frontend validateField).

| Run | Peak, AU | Truth, AU | Error | Peak / median |
|---|---|---|---|---|
| Circular orbit model | 30.28 | 29.89 | +1.3 % | 72 |
| Parallax-only (static) baseline | 42.52 | 29.89 | +42 % | 72 |
| Empty sky, dec0 + 1° | no peak | — | — | 1.0 |

## E3a. Neptune and Uranus observing windows + archive coverage (DONE)
`poc/find_windows.py`, `poc/probe_coverage.py`. Elongation 85–95°.

| Body | Window | Dates | SPHEREx exposures | Collection |
|---|---|---|---|---|
| Neptune | 1 | 2025-06-19 … 06-28 | 44 | spherex_dr1 |
| Neptune | 2 | 2025-12-17 … 12-25 | 27 | spherex_dr1 |
| Neptune | 3 | 2026-06-21 … 07-01 | 86 | spherex_qr3 |
| Uranus | 1–3 | 2025-08 / 2026-02 / 2026-08 | present (exclude *_cube products) | dr1 / qr3 |

## E4a. Neptune sanity check on a real exposure (DONE)
Exposure 2025W25_2A_0500_1, detector D1, June 2025. Cutout centred on the JPL/astropy ephemeris position
at the exposure time: a bright compact source sits on the crosshair (poc/out/sanity_window1.png).
Identity check against a June-2026 exposure of the same sky: PENDING.

## E5b. Detectability figure (DONE)
docs/figures/detectability.png/.svg, data docs/limits.json (schema limits-1.0).
Message: the predicted Planet Nine box (290–800 AU, V 21.9–22.7) lies below the single-frame (AB 18.4),
100-frame (20.9) and 300-frame (21.5) limits → not expected to be detectable by SPHEREx alone.

## E6. Ephemeris cross-check: astropy builtin vs JPL Horizons (DONE)
Neptune, 2025-06-01: RA differs by 4.6″, Dec by 1.4″ (< 1 SPHEREx pixel of 6.15″); r = 29.8910 vs 29.8903 AU.
Results computed with the astropy fallback (inside agent sandboxes) are therefore valid. Final numbers on
slides are quoted against JPL Horizons (queried from the team laptop).

## E4b. Identity check — Neptune is a mover, not a star (DONE, real data)
Same sky position (Neptune's ephemeris position, June 2025) in two epochs:
window 1 (June 2025): peak within 3 px = 77.8 MJy/sr; window 3 (June 2026): 0.43 MJy/sr (background σ 0.91).
The source is gone a year later while field stars stay → it is Neptune. Figure: poc/out/identity_check.png.

## E4c. Focus curve on real data, v1 (FAILED — diagnosed)
Noise estimated from the difference image (S/N up to 1e5, invalid); templates at a different wavelength
leave star residuals (control shows peaks); 571 steps skipped incl. near 29.9 AU. Fix in v2: VARIANCE-based
noise, wavelength-matched templates (|Δλ|/λ ≤ 2 %), skip diagnostics, SOURCE-flag test.

## E3. PoC A — Honest Blink on real SPHEREx (M101: PASS; NEP: rerun; ECL: downloading)
Owner: Data Engineering. M101: 12 honest pairs (|Δλ|/λ ≤ 2 %, Δt ≥ 150 d).
Difference residual: honest pairs 1.03σ vs naive pairs 1.21σ → matched-wavelength comparison is consistent
with noise; mismatched wavelength adds ~20 % spurious "change". Go/No-Go #1: PASS.
NEP: 0 pairs due to a pass-assignment bug (poles are observed continuously) — fix: pair by Δt ≥ 150 d only.
TODO: pair counts per group, spread (16–84 %), bootstrap error on the difference, residual vs Δλ/λ plot.

## E3 update — H1 PASS (15:30)
M101: 12 honest pairs; NEP (fixed pairing, Δt ≥ 150 d): 12 honest pairs. ECL: pending (network).
Criterion "≥ 3 honest pairs in 2 of 3 fields" — met. Residual (M101): honest 1.03σ vs naive 1.21σ.

## E1b. Parallax-only bias flips sign with season (DONE)
| Pair | Model (parallax+orbit) | Parallax-only |
|---|---|---|
| Neptune Jun→Dec 2025 | 29.97 AU (+0.3 %) | 41.98 AU (+40.5 %) |
| Neptune Dec 2025→Jun 2026 | 29.88 AU (−0.0 %) | 23.21 AU (−22.3 %) |
| Uranus Aug 2025→Feb 2026 | 19.38 AU (−0.7 %) | 30.23 AU (+54.9 %) |
| Uranus Feb→Aug 2026 | 19.49 AU (+0.1 %) | 14.37 AU (−26.2 %) |
The parallactic shift reverses between the two half-year pairs; prograde orbital motion does not.
Our model stays within 0.7 %. Synthetic dial at t0 = 2025-06-24: model 29.72 AU (−0.6 %),
parallax-only 41.78 AU (+40 %), empty sky no peak. Supersedes the t0 = 2025-06-10 numbers in E2b.

## E4d. Focus curve on real data, v2 (NOT FEASIBLE on full grid — documented)
VARIANCE-based noise and wavelength-matched templates (|Δλ|/λ ≤ 2 %) implemented (commit dcb1473).
Most grid steps skipped: no_lambda_match / no_matched_stars / no_window2_coverage. Reason: across
15–1000 AU the predicted position spans degrees of sky, and a same-wavelength template is needed at every
position. Decision: full-range dial shown on synthetic data (labelled); real data validated by astrometry (E4e).

## E4e. PoC B-lite — astrometric distance of Neptune from REAL SPHEREx images (historical 9-pair run)
Neptune centroided in SPHEREx Level 2 exposures, June 2025 (window 1) and December 2025 (window 2), detectors D1–D3;
9 exposure combinations. Measured positions agree with JPL Horizons to 0.7–2.0″ (< 1/3 SPHEREx pixel).
| Model | Distance | Error vs JPL 29.89 AU |
|---|---|---|
| Parallax + circular orbit (ours) | 29.94 AU | +0.16 % (spread over 9 pairs below the 0.3 % grid step) |
| Parallax only | 41.60 AU [41.44–41.94] | +39 % |
Residual at the minimum ≈ 80″ (~13 px), the known circular-orbit approximation residual (cf. E1).
Figure: poc/out/astrometric_residual.png. Reproduce: `PYTHONPATH=pipeline:poc python poc/poc_b_astrometry.py` (JSON produced in commit `dbbf7ef`). This is the historical 9-pair result; the headline is the 265-pair median below.

## Go/No-Go #2 (17:00) — PARTIAL GO
Real data: distance recovered from SPHEREx images to 0.2 %; Neptune confirmed as a mover (E4b).
Full-range dial: synthetic demo (labelled). Limitation stated: needs same-wavelength templates per sky position.

## E4f-E4h. Real-data validation, astrometric B-lite (2026-11-14)

Headline: E4f Neptune June→December, all 265 exposure pairs. The following exact commands and commits produced each JSON:

Refined headline distance and uncertainty: 29.949243 AU; U=0.03 AU. Bootstrap 68% CI [29.948053, 29.950459] AU; centroid sigma=0.021034 AU; positional sensitivity S=278.220245 arcsec/AU; fit_distance geomspace step=0.069966 AU. Pair scatter remains separately reported in poc/out/astrometric_distance_all.json.

| Run | Pairs | Truth (JPL) | Ours (circular) | Error | Parallax-only | Error |
|---|---|---|---|---|---|---|
| E4f Neptune Jun->Dec, all exposures | 265 | 29.89 AU | 29.95 AU (p16-p84 29.93-29.96) | +0.22% | 40.59 AU | +35.8% |
| E4g Uranus Aug->Feb (positive control) | 9 | 19.50 AU | 19.39 AU | -0.54% | 29.31 AU | +50.4% |
| E4h Neptune Dec->Jun (season flip) | 9 | 29.88 AU | 29.87 AU | -0.06% | 22.99 AU | -23.1% |

- E4f headline: `PYTHONPATH=pipeline:poc python poc/poc_b_astrometry.py --all-local` — `poc/out/astrometric_distance_all.json`, commit `a3b038f`.
- E4g Uranus: `PYTHONPATH=pipeline:poc python poc/poc_b_astrometry.py --body uranus` — `poc/out/astrometric_distance_uranus.json`, commit `14795fd`.
- E4h Neptune W2→W3: `PYTHONPATH=pipeline:poc python poc/poc_b_astrometry.py --body neptune --epoch-a 2 --epoch-b 3` — `poc/out/astrometric_distance_neptune_w23.json`, commit `48687de`.

Conclusions:
- Recovery is within 0.6% for two planets and both seasonal orders.
- Parallax-only bias flips sign with season (+36% vs -23%), as predicted by validate_geometry.
- 265 Neptune pairs give a tight distribution: the 9-pair result was not a lucky pick.
