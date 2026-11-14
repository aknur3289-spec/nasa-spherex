# Numbers for website and slides (single source of truth)

## HEADLINE (use these on site/slides)

- Neptune: 29.95 AU vs JPL 29.89 AU (heliocentric distance; truth is the mean of the window-1 and window-2 ephemeris r_au values), +0.2%, 265 exposure pairs. Unrounded error: +0.21564491688982756%; documentation rounding: +0.22%.
- Uranus: 19.39 AU vs JPL 19.50 AU, −0.5%. Unrounded error: −0.5375286289975401%; documentation rounding: −0.54%.
- Parallax-only distance errors across the validated seasonal pairs: −23% to +50%.
- Neptune headline uncertainty: 29.95 ± 0.00 AU (bootstrap), centroid-propagated ± 2.22 AU; pair scatter is std 0.0182 AU (p16–p84 29.9325–29.9625 AU), not the bootstrap uncertainty.

The former 29.94 AU Neptune value is historical/superseded: it is the 9-pair June–December result, 29.935715308957782 AU vs 29.88803609144112 AU (+0.1595260972343264%, +0.16% to two decimals). It is not the headline.

The dial table uses ONE exposure pair: ref 2025W25_2A_0500_1 → target 2025W51_1A_0485_1. At 0.1 AU grid spacing, the model minimum is 29.9 AU and the parallax-only minimum is 41.6 AU. These are single-pair table values, not the 265-pair headline.

## Additional documented measurements

| Measurement | Value | Evidence |
|---|---:|---|
| Neptune all-pairs circular median | 29.95 AU; +0.22% | astrometric_distance_all.json; unrounded error +0.21564491688982756% |
| Neptune all-pairs parallax-only median | 40.59 AU; +35.8% | astrometric_distance_all.json |
| Uranus circular median | 19.39 AU; −0.54% | astrometric_distance_uranus.json; unrounded error −0.5375286289975401% |
| Uranus parallax-only median | 29.31 AU; +50.4% | astrometric_distance_uranus.json |
| Neptune W2→W3 circular median | 29.87 AU; −0.06% | astrometric_distance_neptune_w23.json; unrounded error −0.0582995166831021% |
| Neptune W2→W3 parallax-only median | 22.99 AU; −23.1% | astrometric_distance_neptune_w23.json |
| Identity check, June 2025 | 77.8 MJy/sr | EXPERIMENTS E4b; peak within 3 px |
| Identity check, June 2026 | 0.43 MJy/sr | EXPERIMENTS E4b; background σ=0.91 MJy/sr |
| Measured-to-Horizons astrometric offsets | see SCIENCE_SUMMARY.md | Per-exposure centroid offsets |

See [SCIENCE_SUMMARY.md](SCIENCE_SUMMARY.md) for the measurement method, uncertainty estimates, and limitations.

## Detectability context

Single-frame limit AB 18.4; Planet Nine reflected-light estimate V=21.9–22.7 from arXiv:2507.22297. V is used as a near-IR proxy, and methane absorption is ignored in the simple limit calculation; see docs/limits.json and EXPERIMENTS.md.
