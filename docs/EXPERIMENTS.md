# Experiments

## PoC A — Honest Blink

Run: 2026-11-14T10:13:04+00:00. Offline input paths: `data/meta/{m101,nep,ecl}/epochs.csv` and local FITS cutouts; missing inputs are shown in the table.

Passes use gaps >45 days. Strict pairs require Δλ ≤2% and Δt ≥150 days; loose pairs allow Δλ ≤5%. Pair counts are selected outputs (cap 12 per field). R uses MAD of the reprojected, masked difference divided by median combined variance noise; B scale is the median positive A/B ratio in the brightest 2% of valid A pixels.

| Field | Frames | Passes | Strict | Loose | R honest | R naive | Status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| m101 | 169 | 3 | 12 | 12 | 1.029 | 1.214 | ok |
| nep | 159 | 1 | 0 | 0 | — | — | ok |
| ecl | 0 | 0 | 0 | 0 | — | — | missing_epochs |

H1: **FAIL**. Success requires at least 3 strict pairs in at least 2 of 3 fields.

Per-detector selected pair counts (strict/loose, no 12-pair field cap):
- m101: D1 34/36, D2 50/51, D3 37/40.
- nep: D1 0/0, D2 0/0, D3 0/0.
- ecl: none.

Limitations: NEP has one pass under the 45-day gap rule, so no cross-pass pairs. ECL has no local epochs.csv; no network or deep-collection search was attempted. The M101 residual pairs use different detectors and dates. Residuals are diagnostic for the selected pairs, not a controlled significance test.
