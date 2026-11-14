# PoC B: Neptune distance dial on real SPHEREx data

`realdata.py` is temporary access code; the teammate-owned `pipeline/spx/io.py`
will replace it. It discovers the SPHEREx collections from IRSA SIA2 and reads
only bounded `IMAGE` and `FLAGS` sections. Data source order is local files,
anonymous S3 using SIA `cloud_access`, HTTPS range reads, then an IRSA cutout
with 20/60/120 second retry waits. S3 sections are cached in gitignored
`data/raw/sections/`, keyed by obs_id, detector, and section bounds. Detector is
included because multiple detector files share an obs_id.

Run with the shared environment:

```sh
source ~/nasa-spherex/.venv/bin/activate
PYTHONPATH=pipeline python poc/poc_b_dial.py
```

## Identity check

The same sky position is bright in the window-1 stamp and blank in the window-3
stamp. Peak values within 3 pixels of center are 77.7839 MJy/sr (window 1) and
0.4294 MJy/sr (window 3); the later peak is only 0.91 robust annulus sigmas
above its local background. This supports that the window-1 source moved away.
The comparison is `out/identity_check.png`.

## Grid results

The grid had 318 trial distances and completed all three runs in 690.3 seconds.
The distance estimates did not meet the success criteria: none is within 15%
of the 29.8898 AU ephemeris distance, and the empty-sky control has a strong
peak. These are measured outputs; no parameters were tuned to improve them.

| Run | Peak distance (AU) | Error | Peak / median | Steps used / skipped |
|---|---:|---:|---:|---:|
| Circular | 194.85 | +551.89% | 37.28 | 115 / 203 |
| Static baseline | 173.85 | +481.64% | 2276.45 | 143 / 175 |
| Empty-sky control | 88.26 | +195.28% | 2036.93 | 125 / 193 |

Circular and control skips were due to insufficient unflagged pixels. Static
also skipped 12 steps with no window-2 coverage. Peak plots and detailed steps
are `out/focus_neptune.png`, `out/peak_stamp.png`, and
`out/focus_neptune.json`.

## Data source and flags

For the full grid, 13 exposure sections were read from anonymous S3, zero from
local files, zero from HTTPS, and zero from the IRSA fallback. Each section was
at most 1200 × 1200 pixels and covered all planned stamps for that exposure.
The earlier sanity and identity cutouts remain in `data/raw/`; no full FITS
exposures were downloaded. FITS flag names (`MSKNnnnn`) drive the requested
BAD, SATURATION, and never-mask groups.

JPL Horizons returned HTTP 502 for the batched window-3 ephemerides; the
validated Horizons helper used its astropy fallback. The IRSA 503 cutout failures
from the earlier access attempt were bypassed by the successful S3 section path.

## Variance and wavelength matched rerun (v2)

Run the revised analysis with:

```sh
source ~/nasa-spherex/.venv/bin/activate
PYTHONPATH=pipeline:poc python poc/poc_b_dial_v2.py
```

The v2 scorer uses `VARIANCE_target + scale² × VARIANCE_template` for aperture
noise, and selects a same-family window-3 template by its WCS-WAVE value at the
target position (2% match, then 5% fallback). The scale is the median of the
five brightest matched-star flux ratios. SIA track queries are cached under
gitignored `data/raw/sia_track_cache_v2.json`; sections and wave tables use the
section cache. The v2 chart and full per-step ledger are
`out/focus_neptune_v2.png` and `out/focus_neptune_v2.json`;
`out/peak_stamp_v2.png` shows the circular-run peak when one exists.

The sanity stamp has SOURCE on Neptune and all three brightest nearby stars, so
the conditional SOURCE-unflagged metric was not applicable. The v2 run used
variance-based S/N only. It completed in 699.1 seconds and downloaded zero new
sections on the final cached run (nine sections served from S3). No circular or
static peak met the 15% distance criterion; the control had no matched template
steps after the 5% wavelength check. Full skip reasons and summaries are in the
v2 JSON.
