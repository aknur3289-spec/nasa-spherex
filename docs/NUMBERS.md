# Numbers for website and slides (single source of truth)

| Quote | Value | Source | Note |
|---|---|---|---|
| Neptune distance, our model, real SPHEREx images | 29.94 AU | EXPERIMENTS E4e; poc/out/astrometric_distance.json | median over exposure pairs |
| Neptune distance, JPL Horizons | 29.89 AU | same file, truth_r_au = 29.888 | |
| Error of our model | 0.2 % | (29.936 − 29.888) / 29.888 = 0.16 % | quote "0.2 %"; 29.94 vs 29.89 rounded gives 0.17 % — both round to 0.2 % |
| Parallax-only model, same data | 41.6 AU | E4e, static median 41.60 | |
| Parallax-only error | +39 % | (41.60 − 29.89) / 29.89 = 39.2 % | |
| Identity check, June 2025 | 77.8 MJy/sr | E4b, peak within 3 px | |
| Identity check, June 2026 | 0.43 MJy/sr | E4b | background σ = 0.91 → consistent with empty sky |
| Astrometric offset from JPL | 0.7–2.0″ | E4e | < 1/3 SPHEREx pixel (6.15″) |
| Parallax-only bias range by season | −26 % to +55 % | E1b | our model within 0.7 % |

## Real-data distance recovery (B-lite, 2026-11-14)
- Neptune, 265 pairs: 29.95 AU vs JPL 29.89 (+0.22%); parallax-only 40.59 (+35.8%)
- Uranus, 9 pairs: 19.39 AU vs JPL 19.50 (-0.54%); parallax-only 29.31 (+50.4%)
- Neptune Dec->Jun, 9 pairs: 29.87 AU vs JPL 29.88 (-0.06%); parallax-only 22.99 (-23.1%)
- Parallax-only error range: -23% to +50%, sign set by season
