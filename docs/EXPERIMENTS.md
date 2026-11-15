# Experiments

## PoC A — Honest Blink

Run: 2026-11-14T11:38:32+00:00. Offline input paths: `data/meta/{m101,nep,ecl}/epochs.csv` and local FITS cutouts; missing inputs are shown in the table.

Display passes use gaps >45 days; a single continuous cluster spanning >150 days uses 182.6-day segments from its first MJD. Strict pairs require Δλ ≤2% and Δt ≥150 days; loose pairs allow Δλ ≤5%. Pair counts are selected outputs (cap 12 per field). R uses MAD of the reprojected, masked difference divided by median combined variance noise; B scale is the median positive A/B ratio in the brightest 2% of valid A pixels.

| Field | Frames | Passes | Strict | Loose | R honest | R naive | Status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| m101 | 169 | 3 | 12 | 12 | 1.029 | 1.214 | ok |
| nep | 159 | 3 | 12 | 12 | 0.917 | 0.878 | ok |
| ecl | 140 | 3 | 12 | 12 | 1.951 | 0.987 | ok |

H1: **PASS**. Success requires at least 3 strict pairs in at least 2 of 3 fields.

Per-detector selected pair counts (strict/loose, no 12-pair field cap):
- m101: D1 34/36, D2 50/51, D3 37/40.
- nep: D1 23/39, D2 19/29, D3 12/26.
- ecl: D1 38/38, D2 39/39, D3 36/36.

Limitations: Residuals are diagnostic for the selected pairs, not a controlled significance test.

## Neptune dial raw-peak negative result — 2026-11-14

On the cached full-frame sections for `2025W25_2A_0500_1` → `2025W51_1A_0485_1`, choosing the brightest pixel within 20 px of each predicted position gave a false minimum at **36.79 AU with 0.5 px offset**. The JPL target was near 29.89 AU, and the Science astrometric table places its single-pair model minimum near 29.9 AU. A field star, rather than Neptune, can be nearest to the crosshair in a raw frame. This criterion is unsuitable as `neptune-dial.offset_px`; the dial now uses distance to Neptune's measured target-frame centroid. Raw peak offsets remain diagnostic only.

## Blind moving-object test — 2026-11-15

Detector, linking and distance fit run without JPL Horizons; Horizons only grades the result. Neptune found
in 40/48 June and 24/26 December differences; it is the top *mover* track in both windows. Blind distance
**29.93 AU vs Horizons 29.89 AU (0.13 %)**. The SPHEREx `OUTLIER`/`TRANSIENT` flags mark moving sources;
masking them loses 10 of 64 Neptune detections. Injection test: 50 % completeness near 10× pixel noise.
Details and limits: `docs/BLIND_TEST.md`.
