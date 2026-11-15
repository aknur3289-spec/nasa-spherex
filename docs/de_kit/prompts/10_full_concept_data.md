# P10 — Data for the full concept: Timeline, Sky Explorer, mover field, injection inputs
Tool: Claude Code (A, B), Codex (tests). Branch: `data/full`. Start after P05 works (≈17:30). Each part is independent — run A and B in separate worktrees.
Contract rule: everything here is ADDITIVE. Agree the formats with the frontend owner (who owns docs/CONTRACT.md) BEFORE shipping; until then write the files but do not reference them from field.json.

---
## Part A — Timeline + Sky Explorer data
Read AGENTS.md, docs/CONTRACT.md, contracts/DATA_INTERFACES.md.

FILES: `pipeline/build_timeline.py`, `pipeline/tests/test_timeline.py`, outputs `web/public/data/<field_id>/timeline.json`, `web/public/data/<field_id>/t/*.png`, updated `web/public/data/index.json` (only via manifest.update_index — extend it, keep existing keys).

timeline.json (per static field), proposal `timeline_version: "0.1"`:
```json
{ "field_id": "m101", "detector_groups": [
    { "detector": 2, "wl_min_um": 1.10, "wl_max_um": 1.62,
      "frames": [ { "id": "t001", "png": "t/t001.png", "mjd": 60800.1, "obs_time_utc": "...", "survey_pass": 1,
                    "wavelength_um": 1.31, "bad_pixel_fraction": 0.01, "source_url": "...", "in_pair": true } ] } ],
  "passes": [ { "survey_pass": 1, "mid_utc": "...", "n_frames": 37 } ] }
```
- ALL usable frames of the field (cap 120 per detector, evenly in time), sorted by mjd, rendered with the SAME per-detector stretch as field.json frames (reuse render.py). PNG ≤ 99 px; thumbnails, no upscaling.
- `in_pair` marks frames used by honest pairs, so the UI can highlight them on the timeline.
- Honest note for the UI: neighbouring frames in time differ in wavelength — include `wavelength_um` on every frame; do not compute anything "changed" here.

index.json extension (Sky Explorer): add per field `ra_deg`, `dec_deg`, `size_arcmin`, `n_frames`, `n_passes`, `date_min_utc`, `date_max_utc`, `n_pairs_high`, `has_timeline`. Keep `{field_id, kind, title, thumbnail}` unchanged.

TESTS: timeline sorted by mjd; cap respected and evenly spaced; every png exists; index keeps old keys.

## Part B — one "mover" field: a known asteroid or comet crossing a real frame pair
Goal: show REAL motion in Honest Blink (not just stable stars). Known objects only.
FILES: `pipeline/find_mover.py`, entry in `pipeline/fields.yaml`, outputs as a normal static field built by build_field.py.
1. Candidates: use JPL Horizons (astroquery.jplhorizons, location '500') for a short list of numbered bright main-belt asteroids or a comet (the science owner may give names; otherwise pick ~20 numbered asteroids with V 11–15 at the SPHEREx epochs). For each, ephemeris over the mission span.
2. For each candidate find SPHEREx exposures containing it (reuse moving.find_exposures). Need: ≥ 2 exposures in the SAME pass on the same detector with |Δλ|/λ ≤ 2% and Δt ≥ 1 hour (within-pass revisits), so the asteroid moves while stars stay — OR a cross-pass honest pair where the asteroid is present in one frame only.
3. Build the field centred on the mid position; cutout size large enough to contain both positions (≤ 20′). Title "<Asteroid name>: a moving asteroid (known object)". Description states it is a catalogued asteroid with its Horizons designation.
4. For this field ONLY, pair rule exception: allow within-pass pairs with dt ≥ 0.04 d, dlam ≤ 2%; mark them in docs/DATA.md. Ask the frontend owner if pairs[].kind "mover" is accepted; otherwise use trust as usual.
5. Write `data/meta/<id>/mover_track.json`: positions (ra, dec, mjd) from Horizons for each published frame — the UI may draw the known track as an overlay, labelled "JPL Horizons ephemeris".
If nothing qualifies within 60 minutes: stop, report the best near-miss, do not force it.

## Part C — inputs for the science owner's injection test (sensitivity)
FILES: `pipeline/export_injection_inputs.py`, outputs `data/meta/injection/<field_id>.npz` + `README.md`.
For 2 fields (ecl + one more chosen by the science owner) export per honest pair: images A and B on the common grid (float32, MJy/sr, zodi- and median-subtracted, NaN for bad), variance on the grid, bad masks, the grid WCS header as string, frame metadata (mjd, wavelength_um, detector, psf_fwhm_arcsec). No injection here — the science owner injects; anything they render back to the web MUST carry provenance.synthetic = true.

DONE (all parts): pytest green; QA prompt P08 passes on the new outputs; DATA_HANDOFF.md updated with formats and paths; message to the frontend owner with the two JSON examples.
