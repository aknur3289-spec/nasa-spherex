# P08 — Data QA / red team (run before every merge into main and at DATA FREEZE 01:30)
Tool: a FRESH session (Codex or Claude Code) that did not write the code. Read-only except `docs/QA_DATA.md` and `data/meta/qa/`.

---
Read AGENTS.md and docs/CONTRACT.md. You did not write this pipeline. Act as a sceptical astronomer + senior data engineer. Do NOT fix code; report.

RUN
1. `pytest pipeline/tests -q` → paste summary.
2. `python pipeline/build_all.py --offline` → must succeed with zero network calls (run with network disabled if possible, e.g. `HTTPS_PROXY=http://127.0.0.1:9`). Diff the produced field.json against the committed ones.
3. For every `web/public/data/*/field.json`: validate against the schema; check every png exists and opens; every frame has source_url (open 2 random source_urls with HEAD/GET and report status); obs_time_utc matches mjd (±1 s); wavelength inside the detector band; survey_pass consistent with dates; dt_days and dlam_frac recomputed from frames match the stored values (±1e-3); trust labels match thresholds; no frame with bad_pixel_fraction > 0.30 appears in an honest pair; provenance.synthetic == false and no fixture ids in index.json.
4. Build `data/meta/qa/contact.html` (static, local only): for each field, each pair A | B | diff with the badge numbers — so a human can eyeball all pairs in 2 minutes. Flag pairs where A and B look misaligned (cross-correlation peak offset > 1 px) — report offsets.
5. Honesty scan: grep pipeline, fields.yaml titles/descriptions and docs for "discover", "candidate", "Planet X found", "new planet", "detected planet". Any number in docs/DATA.md or EXPERIMENTS.md without a source run → flag.
6. Size: total MB of web/public/data (target < 30 MB), largest file, count of files.
7. Scope: `git diff --stat main...HEAD` — files outside the data-track list in AGENTS.md → flag.

OUTPUT (`docs/QA_DATA.md`): table severity (P0 blocks submission / P1 fix if time / P2 note) | file or field | problem | suggested fix. Then one paragraph: safe to merge / safe to freeze? yes/no and why.
