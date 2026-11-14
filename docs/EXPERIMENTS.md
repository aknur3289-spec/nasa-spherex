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
