# P03 — `pipeline/spx/pairs.py` + PoC A (Honest Blink hypothesis H1)
Tool: Codex for pairs.py + tests; then Claude Code to run PoC A on real data. Branch: `data/pairs`. Needs: epochs.csv from P02 (or a synthetic one for tests).

---
Read AGENTS.md and docs/DATA.md. Implement survey-pass assignment and wavelength-matched pair selection, then run PoC A.

FILES
- `pipeline/spx/pairs.py`, `pipeline/tests/test_pairs.py`
- `poc/poc_a_honest_blink.py`
- `docs/EXPERIMENTS.md` (append section "PoC A")
- outputs in `data/meta/<field_id>/`: `pairs.csv`, `poc_a_summary.json`, `poc_a.png`

pairs.py API
```python
def assign_survey_pass(mjd: np.ndarray, gap_days: float = 45.0) -> np.ndarray
    # cluster sorted times: a new pass starts after a gap > gap_days; passes numbered 1..K per field.
    # Also return/record pass mid-MJD. Do NOT use a fixed 182.6-day formula.
def dlam_frac(wl_a_um: float, wl_b_um: float) -> float   # |a-b| / ((a+b)/2)
def trust_of(dlam: float) -> str                         # high <= 0.02, medium <= 0.05, else low  (ONLY place trust is computed)
def match_pairs(frames: pd.DataFrame, max_dlam_frac=0.05, min_dt_days=150.0, max_pairs=12) -> pd.DataFrame
def naive_pairs(frames: pd.DataFrame, n=3) -> pd.DataFrame
```

match_pairs rules
- Candidates: same detector; both status == ok and target_bad == False; different survey passes; dt_days ≥ min_dt_days; dlam_frac ≤ max_dlam_frac.
- Sort by dlam_frac asc, then bad fraction sum asc, then dt desc. Greedy pick with diversity: each frame in at most 2 pairs; prefer covering different pass combinations (1–2, 1–3, 2–4 …) before repeating one.
- Output columns: a, b (frame_ids), detector, wl_a_um, wl_b_um, dlam_frac, dt_days, pass_a, pass_b, trust, kind="honest".

naive_pairs rules (the "what everyone else does" baseline for the Naive/Honest switch)
- kind="naive_time": consecutive frames in time order on the same detector (typical naive blink) with the LARGEST wavelength difference — shows colour change, not time change.
- kind="naive_gap": same dt ≥ min_dt_days as an honest pair but the largest dlam_frac. trust from trust_of (will be low).

PoC A script (`python poc/poc_a_honest_blink.py --fields m101 nep ecl`)
For each field (coordinates from pipeline/fields.yaml) that already has epochs.csv:
1. Assign passes, run match_pairs (strict 0.02 and loose 0.05) and naive_pairs.
2. Metric H1: number of pairs with dlam ≤ 2% and dt ≥ 150 d. Success = ≥ 3 such pairs in ≥ 2 of 3 fields.
3. Residual check (validation number for the jury): for the best honest pair and the best naive_gap pair, reproject B onto A's WCS (`reproject.reproject_interp`), compute `R = robust_std(A − s·B) / noise`, where s = median ratio over bright unmasked pixels (top 2 %) — report R_honest and R_naive. Expect R_honest < R_naive.
4. `poc_a.png` (matplotlib, 2 rows): row 1 honest pair A | B | A−B; row 2 naive pair A | B | A−B; same asinh stretch inside each row; titles with λ, date, Δλ %, Δt. Plus a small panel: wavelength vs MJD scatter coloured by detector, honest pairs drawn as lines.
5. `poc_a_summary.json`: per field → n_frames, n_passes, pass mid-dates, n_pairs_strict, n_pairs_loose, best pair, R_honest, R_naive, verdict.
6. Append to docs/EXPERIMENTS.md: date/time, inputs, the table of numbers, verdict for H1, what failed. Numbers only from the run — no edits by hand.

IF H1 FAILS: rerun with max_dlam_frac=0.05 and report; try the deep collection for NEP; report how many pairs exist per detector so the science lead can choose detectors.

TESTS: synthetic frames → passes split by gaps; thresholds respected; no same-pass pairs; each frame ≤ 2 uses; trust boundaries (0.02 → high, 0.0201 → medium, 0.05 → medium, 0.0501 → low); naive pairs have larger dlam than honest.

DONE: pytest green; poc_a_summary.json + poc_a.png for ≥ 2 real fields; EXPERIMENTS.md updated. Report the H1 verdict in one line.
