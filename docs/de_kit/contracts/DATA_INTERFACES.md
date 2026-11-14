# Data interfaces (Data Engineering ↔ Science ↔ Frontend)

## 1. To the frontend: `web/public/data/` (CONTRACT.md v1.0, owned by the tech lead — unchanged)
```
web/public/data/
  index.json                      # [{field_id, kind, title, thumbnail}]
  m101/ field.json  f001.png …  thumb.png  [diff_f003_f041.png]
  nep/  …
  neptune-2025/        field.json (kind "dial") d001.png …
  neptune-2025-blank/  field.json (kind "dial")
```
Facts the frontend must know (put in docs/DATA_HANDOFF.md):
- PNG ≈ 99×99 px for 10′ (6.15″/px) → render with `image-rendering: pixelated`, scale ×4–6.
- 8-bit grey + alpha; transparent = flagged pixel.
- Both frames of every honest pair share one stretch → blink/slider is fair. Pairs ordered: high → medium → naive.
- Trust is computed only in the pipeline.

### Additive proposals (v1.1) — ask the tech lead, do NOT ship without approval
| field | type | why |
|---|---|---|
| `pairs[].kind` | `"honest" \| "naive_time" \| "naive_gap"` | Naive/Honest switch picks the right pair without guessing |
| `pairs[].diff_png` | string, optional | difference computed on calibrated floats (fairer than |A−B| of 8-bit PNGs in the browser) |
| `frames[].bandwidth_um` | number | shown in FrameInfo |
| `frames[].collection` | `"spherex_dr1" \| "spherex_qr3"` | provenance |
If rejected: client computes difference from PNGs as planned; files stay unused.

## 2. To the science lead: `data/meta/<id>/` (git-ignored except .json/.md/.png summaries)
| file | content |
|---|---|
| `raw_index.csv` | every exposure found + download status (P01) |
| `epochs.csv` | one row per usable frame: frame_id, obs_id, detector, collection, processing_version, mjd, obs_time_utc, wavelength_um, bandwidth_um, x_pix, y_pix, bad_pixel_fraction, target_bad, zodi_median_mjysr, noise_mad_mjysr, survey_pass, source_url, local_path, downloaded_utc, status (+ eph_* columns for moving targets) |
| `pairs.csv` | a, b, detector, wl_a_um, wl_b_um, dlam_frac, dt_days, pass_a, pass_b, trust, kind |
| `passes.json` | survey passes: mid date, counts, elongation (moving targets) |
| `poc_a_summary.json`, `poc_a.png` | PoC A numbers + figure |
| `HANDOFF.md` | ≤ 30 lines, what/where/problems |
Raw slim FITS: `data/raw/<id>/*.fits` (no EPSF HDU).

## 3. From the science lead (inputs you consume, never edit)
- `pipeline/spx/geometry.py: predict_radec(...)`
- SNR-at-crosshair function + search radius, detector choice, model string for dial.model
- approval of fields.yaml and of every number that goes on slides (docs/EXPERIMENTS.md)
