# P09 — Short operational prompts (copy as needed)

## A. Fix loop (when a run fails)
```
Read AGENTS.md. The command below failed. Reproduce it, find the root cause, fix it with the smallest change inside the files you own, add a regression test, rerun. Do not change thresholds, schemas or other owners' files to make it pass. If the cause is IRSA being down/slow, say so and switch to the fallback method (TAP→SIA→cloud) instead of patching around it.
COMMAND: <paste>
OUTPUT: <paste last 40 lines>
```

## B. Add one more gallery field (after 3 fields work)
```
Read AGENTS.md. Add field <id> to pipeline/fields.yaml (ra=<>, dec=<>, title "<>", description "<one honest sentence>", detectors [1,2,3]). Run `python pipeline/build_field.py --id <id>`. Report frames/passes/pairs. If it has < 2 honest pairs, set enabled: false and tell me why. Do not touch any code.
```

## C. Coordinates of a named object (never hard-code from memory)
```
Read AGENTS.md. Resolve "<object name>" with astroquery SIMBAD (or Sesame). If it has proper motion, propagate to epoch 2026.0 with SkyCoord.apply_space_motion using SIMBAD pmra/pmdec/plx/rv. Print ra_deg/dec_deg at J2000 and at 2026.0, magnitude J/K, and whether it is likely saturated for SPHEREx (flag if K < 9 — confirm by checking target_saturated after fetch). Write nothing except a proposed fields.yaml entry in your answer.
```

## D. Frontend handoff note
```
Read AGENTS.md, docs/CONTRACT.md and every web/public/data/*/field.json. Write docs/DATA_HANDOFF.md (≤ 40 lines) for the frontend dev: list of fields with kind, frame count, pairs by trust, PNG pixel size (they must upscale with image-rendering: pixelated), which fields have zero honest pairs, which extra files exist (diff_*.png, thumb.png) and whether the contract references them, and 3 sentences of plain-English copy per field the designer may use (no claims beyond the data).
```

## E. Submission data section
```
Read docs/DATA.md, docs/EXPERIMENTS.md and every field.json provenance. Draft the "NASA Data" and "Space Agency Partner & Other Data" paragraphs for the Space Apps project page in English: SPHEREx Level 2 Spectral Images via NASA/IPAC IRSA (collections actually used, how many frames, date range, processing versions), JPL Horizons/astropy for ephemerides, every Python library. Leave DOI as "[DOI from IRSA release page]" unless docs/DATA.md contains a verified one. Max 150 words each. No claims of discovery.
```

## F. Status report (every 2 hours, paste into team chat)
```
Read git log since <time>, docs/DATA.md, docs/QA_DATA.md, data/meta/*/poc_a_summary.json. Write a 6-line status: done / in progress / blocked / numbers (fields built, frames, honest pairs) / next 2 hours / what I need from whom.
```
