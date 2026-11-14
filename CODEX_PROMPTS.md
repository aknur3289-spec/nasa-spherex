# Codex prompts for Participant 1 (paste the PROJECT CONTEXT block from the plan, section 15, on top)

## Prompt 1 — SPHEREx data access (pipeline/spx/io.py) — do this FIRST
OBJECTIVE: implement pipeline/spx/io.py with the exact signatures from docs/CONTRACT.md "Module interfaces":
sia_search(ra, dec, radius_deg=0.02, mjd_range=None) -> list[dict]
fetch_cutout(row, ra, dec, size_deg, outdir="data/raw") -> Path | None
read_frame(path, ra, dec) -> (image, bad_mask, wcs, wavelength_um_at_(ra,dec), (mjd, ...))
Follow the IRSA SPHEREx cutouts tutorial (pyvo SIA2 on collection spherex_qr / spherex_dr1, cutout via
?center=ra,dec&size=deg on the access_url). Read wavelength at the pixel from the spectral WCS (the
"WCS-WAVE" alternate WCS / lookup table extension per the IRSA tutorial). Mask = FLAGS != 0.
Cache: never download a file twice. Retry 2x with backoff, then skip and log.
FILES: pipeline/spx/io.py, pipeline/tests/test_io.py (offline tests on one saved FITS), poc/poc_a_honest_blink.py
DONE: `python poc/poc_a_honest_blink.py --ra 210.80227 --dec 54.34895` writes poc/epochs.csv
(columns: file, obs_id, mjd, detector, wavelength_um, bad_frac, source_url) and poc/poc_a.png (two frames).

## Prompt 2 — pairs (pipeline/spx/pairs.py)
match_pairs(frames, max_dlam_frac=0.02, min_dt_days=150) -> list of {a, b, dlambda_frac, dt_days, trust};
trust high <= 0.02, medium <= 0.05, else low. Sort by dlambda_frac. Tests with synthetic frame lists.

## Prompt 3 — PoC B on real data (poc/poc_b_dial.py)
Use pipeline/spx/geometry.py, focus.py (focus_curve, dial_grid, summarize), horizons.py — DO NOT modify them.
1. ephem("neptune", ...) -> find SPHEREx frames covering Neptune in two survey passes ~6 months apart (sia_search
   with radius 0.05 deg around the ephemeris position, per pass window).
2. Reference = Neptune position in pass A frame (t0). For each d in dial_grid(15, 1000, 15):
   predicted (ra, dec) at t1 -> cutout from the pass-B frame at that position MINUS cutout of the same sky from a
   different pass (same wavelength if possible, reprojected to the same grid) -> difference stamp.
3. focus_curve(...) -> summarize(steps, truth_au) -> poc/focus_neptune.json; repeat with orbit="static"
   (baseline), with dec0 + 1 deg (empty-sky control), and for Uranus (positive control).
4. Append results to docs/EXPERIMENTS.md section E4.
Cache cutouts: neighbouring grid steps are ~15 px apart, so one 10' cutout covers several steps.
