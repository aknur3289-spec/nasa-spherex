# P07 — `pipeline/build_dial.py`: package the Distance Dial field (kind "dial")
Tool: Claude Code. Branch: `data/dial`. START ONLY AFTER Go/No-Go #2 (science lead confirms Neptune focuses at its distance in poc_b). Science review of the output: science lead.

---
Read AGENTS.md, docs/CONTRACT.md (dial block), docs/EXPERIMENTS.md (PoC B result you must reproduce), poc/poc_b_dial.py, and `data/meta/neptune/HANDOFF.md`.

INPUT DEPENDENCIES (do not modify)
- `pipeline/spx/geometry.py: predict_radec(ra0, dec0, t0, d_au, times, orbit="circular")` — science lead
- the SNR-at-crosshair function used in poc_b (import it; if it lives only in poc/, copy it into `pipeline/spx/snr.py` UNCHANGED and note the source commit)
- io.py, frame.py, render.py, manifest.py, moving.py

FILES: `pipeline/build_dial.py`, `pipeline/spx/snr.py` (only if copying), `pipeline/tests/test_dial.py`, outputs in `web/public/data/<id>/`

CLI
`python pipeline/build_dial.py --id neptune-2025 --target neptune --pass-a <n> --pass-b <m> --steps 48 --dmin 15 --dmax 1000`
`python pipeline/build_dial.py --id neptune-2025-blank --target neptune-blank --pass-a <n> --pass-b <m> ...` (negative control, identical settings)

STEPS
1. Reference frame: from pass A, the exposure with the lowest bad fraction near the body (detector chosen by science lead, default the one used in poc_b). (ra0, dec0, t0) = ephemeris at that exposure (allowed: this is "we saw the object here in frame A").
2. Distance grid: log-spaced dmin..dmax (steps), plus 12 extra steps between 0.8× and 1.25× of the coarse peak (second pass).
3. For each distance d: pred = predict_radec(ra0, dec0, t0, d, t) where t = a pass-B time. Find a pass-B exposure on the SAME detector that contains pred (io.search_frames with mjd_range = pass B window), choose the one closest in wavelength to the reference frame; RECOMPUTE pred at that exposure's exact MJD and check it is still inside; fetch a 10′ cutout centred on pred (cached). Different d → different exposures is expected (at 15 AU the shift is > 4°).
4. snr + offset_px at the crosshair with search_radius_px from the science lead (default 20). PNG of every step with ONE common stretch for all steps (render.stretch_params over all step images).
5. field.json kind "dial": frames = reference + step frames (full provenance each), dial.reference_frame, dial.model (string from science lead), dial.search_radius_px, dial.steps sorted by distance [{distance_au, frame, pred{ra_deg, dec_deg}, snr, offset_px}], dial.peak_distance_au (argmax snr — no smoothing, no tuning), dial.truth {distance_au: ephemeris r_au at t0, source}, dial.negative_control_field, provenance.
6. Print: peak distance, truth, % error, peak/median snr, n steps with no covering exposure. Compare with docs/EXPERIMENTS.md; if different by > 5 %, STOP and report to the science lead.

FORBIDDEN: using the body's true orbit/ephemeris for pass-B predictions; changing thresholds to move the peak; dropping steps that "look bad". Steps without a covering exposure: keep the step with frame=null only if the contract allows null, else skip and list them in the summary.

TEST (offline): with astropy builtin ephemeris, predict_radec at the true distance lands within 150″ of Neptune and Uranus at the pass-B time; at 0.7× and 1.4× it is > 10′ away (this tests integration, not geometry internals).

DONE: both fields validate; summary numbers match EXPERIMENTS.md; science lead signs off in docs/EXPERIMENTS.md.
