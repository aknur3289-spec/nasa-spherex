# Numbers for website and slides (single source of truth)

## HEADLINE (use these on site/slides)

- Neptune: 29.95 AU vs JPL 29.89 AU (heliocentric distance; truth is the mean of the window-1 and window-2 ephemeris r_au values), +0.2%, 1,007 exposure pairs, U=0.03 AU. Unrounded error: +0.20010079908886771%; documentation rounding: +0.20%.
- Uranus: 19.42 AU vs JPL 19.50 AU, −0.4%, 570 exposure pairs, U=0.02 AU. Unrounded error: −0.41599482736459487%; documentation rounding: −0.42%.
- Parallax-only distance errors across the validated seasonal pairs: −23.10% to +48.60% (−23.1% to +48.6% on site/slides).
- Neptune refined distance: 29.947842 AU; U=0.03 AU (max of bootstrap half-width and centroid sigma, rounded up). Bootstrap 68% CI [29.947141, 29.948924] AU; centroid sigma 0.020744 AU; positional sensitivity S=274.940737 arcsec/AU; fit grid step 0.069966 AU. Pair scatter is reported separately in the full-run JSON.

The former 29.94 AU Neptune value is historical/superseded: it is the 9-pair June–December result, 29.935715308957782 AU vs 29.88803609144112 AU (+0.1595260972343264%, +0.16% to two decimals). It is not the headline.

The dial table uses ONE exposure pair: ref 2025W25_2A_0500_1 → target 2025W51_1A_0485_1. At 0.1 AU grid spacing, the model minimum is 29.9 AU and the parallax-only minimum is 41.6 AU. These are single-pair table values, not the 1,007-pair headline.

## Additional documented measurements

| Measurement | Value | Evidence |
|---|---:|---|
| Neptune full-set circular median | 29.95 AU; +0.20%; U=0.03 AU; 1,007 pairs | astrometric_distance_neptune_full.json; unrounded error +0.20010079908886771% |
| Neptune full-set parallax-only median | 40.93 AU; +36.95% | astrometric_distance_neptune_full.json |
| Uranus full-set circular median | 19.42 AU; −0.42%; U=0.02 AU; 570 pairs | astrometric_distance_uranus_full.json; unrounded error −0.41599482736459487% |
| Uranus full-set parallax-only median | 28.97 AU; +48.60% | astrometric_distance_uranus_full.json |
| Historical Neptune 265-pair median | 29.95 AU; +0.22% | astrometric_distance_all.json; superseded by 1,007-pair E4i |
| Historical Uranus 9-pair median | 19.39 AU; −0.54% | astrometric_distance_uranus.json; superseded by 570-pair E4j |
| Neptune W2→W3 circular median | 29.87 AU; −0.06% | astrometric_distance_neptune_w23.json; unrounded error −0.0582995166831021% |
| Neptune W2→W3 parallax-only median | 22.99 AU; −23.1% | astrometric_distance_neptune_w23.json |
| Identity check, June 2025 | 77.8 MJy/sr | EXPERIMENTS E4b; peak within 3 px |
| Identity check, June 2026 | 0.43 MJy/sr | EXPERIMENTS E4b; background σ=0.91 MJy/sr |
| Measured-to-Horizons astrometric offsets | see SCIENCE_SUMMARY.md | Per-exposure centroid offsets |

See [SCIENCE_SUMMARY.md](SCIENCE_SUMMARY.md) for the measurement method, uncertainty estimates, and limitations.

## Detectability context

Single-frame limit AB 18.4; Planet Nine reflected-light estimate V=21.9–22.7 from arXiv:2507.22297. V is used as a near-IR proxy, and methane absorption is ignored in the simple limit calculation; see docs/limits.json and EXPERIMENTS.md.
