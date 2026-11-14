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
