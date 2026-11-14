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
