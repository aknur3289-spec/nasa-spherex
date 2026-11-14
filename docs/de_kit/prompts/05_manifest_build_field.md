# P05 — `manifest.py` + `build_field.py` + `build_all.py`: static Honest Blink fields for the frontend
Tool: Codex for code + tests; Claude Code for the real build. Branch: `data/build`. Needs: P01–P04 merged, `docs/CONTRACT.md` v1.0 frozen by the tech lead.

---
Read AGENTS.md and docs/CONTRACT.md (field.json schema_version 1.0 — FROZEN; you must not change it). Wire the modules into one reproducible build that writes exactly what the frontend expects.

FILES
- `pipeline/spx/manifest.py`, `pipeline/build_field.py`, `pipeline/build_all.py`, `pipeline/fields.yaml`
- `pipeline/schema/field_v1.schema.json` (ONLY if the tech lead has not provided a schema file; derive it 1:1 from CONTRACT.md and tell the tech lead)
- `pipeline/tests/test_manifest.py`, `pipeline/tests/test_build_offline.py`
- outputs: `web/public/data/<field_id>/field.json`, `*.png`, `thumb.png`, `web/public/data/index.json`, `docs/DATA.md` (section "Built fields")

manifest.py
```python
def validate_field(field: dict) -> None      # jsonschema; raise with the failing JSON path
def write_field(field: dict, outdir: Path) -> None   # validate, then write pretty JSON (sorted keys inside frames)
def update_index(data_root: Path) -> None    # rebuild index.json from all field.json found: [{field_id, kind, title, thumbnail}]
```
Extra checks beyond the schema (fail the build): every frame has source_url, obs_id, mjd, wavelength_um; every pair references existing frames; every png referenced exists on disk; `provenance.synthetic` is false for real builds; trust values come from pairs.trust_of (never recomputed).

build_field.py — pipeline for one field
`python pipeline/build_field.py --id m101 [--offline] [--max-frames 200]`
1. Read the field from fields.yaml (id, title, description, ra, dec, size_arcmin, detectors, collections).
2. fetch_field (skipped with --offline: cache only) → build_epochs → assign_survey_pass → match_pairs + naive_pairs.
3. Choose frames to publish: all frames used by any pair. (Do not publish hundreds of unused frames.)
4. field_grid → to_grid for each published frame → stretch per detector → to_png `fNNN.png`; for each honest pair also `diff_<a>_<b>.png` (keep on disk; reference it in field.json ONLY if the contract has a field for it — otherwise list it in docs/DATA.md for the tech lead to decide).
5. Build field.json exactly per CONTRACT.md: kind "static", frames[] (id, png, obs_time_utc, mjd, survey_pass, detector, wavelength_um, center, bad_pixel_fraction, stretch, source_url, obs_id, processing_version), pairs[] (a, b, dlam_frac, dt_days, trust), provenance (mission "SPHEREx", archive "NASA/IPAC IRSA", collections actually used, doi placeholder string from fields.yaml, downloaded_utc = latest download, pipeline_commit = `git rev-parse --short HEAD`, cached true, synthetic false).
   Pair order: honest high → honest medium → naive (so the client's "first high pair" is the best one).
   Field with zero honest pairs: still write it with the naive pairs only and print a WARNING (the contract says client explains it).
6. `thumb.png` = frame A of the best pair at scale 2. update_index().
7. Print a one-line summary: field, frames published / available, passes, pairs high/medium/low, MB written.

build_all.py: builds every field in fields.yaml (continue on error), then prints a table and exits non-zero if any field failed. `--offline` passes through.

fields.yaml: start from the provided starter file in the kit (m101, nep, ecl + optional ones). Keep `enabled: true/false` per field.

TESTS
- test_manifest: minimal valid field passes; frame without source_url fails; pair referencing a missing frame fails; missing png fails.
- test_build_offline: build a tiny field from 4 synthetic slim FITS in tmp_path (2 passes × 2 wavelengths) with network monkeypatched to raise → field.json validates, 1 honest + ≥1 naive pair, PNGs exist.

DONE: pytest green; `python pipeline/build_all.py` produces ≥ 3 real fields that validate; second run with --offline reproduces byte-identical field.json except downloaded_utc/pipeline_commit; `npm run dev` (ask the tech lead) shows them.
