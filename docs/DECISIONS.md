# Decisions

- Vercel serves the static Vite build. The offline Python pipeline owns science products and never runs inside the web app.
- Contract 1.0 uses a field index plus one self-contained directory per field. Band and FITS are optional for compatibility with early pipeline outputs.
- The Dev3 viewer compares two selected frames. Dial metadata is validated for integration.
- The bundled star fields, metadata, and motion marker are synthetic and are labeled DEMO DATA.
- Contract v1.0 frozen at 2026-11-14 14:00 local time. Additive changes go through v1.1 and breaking changes require v2.
- Display PNGs inpaint masked pixels for readability; analysis uses masked data; mask shown via mask_png toggle.

## 2026-11-14 14:50 — Contract answers from Frontend
- pairs[].kind: REJECTED in field.json (stays in pairs.csv only).
- diff_png: ACCEPTED for v1.1 — optional per pair, relative path "diff/<a>-<b>.png", same size as frames; v1.1 frames require width_px, height_px; schema_version "1.1".
- timeline.json: ACCEPTED for v1.1 — optional file next to field.json: array of {frame_id, obs_time_utc, mjd}, every frame exactly once, sorted by UTC, values copied from field.json.
- v1.0 schema stays; add checks: non-empty description, doi, band (if present); dial: search_radius_px > 0, >= 1 step, offset_px >= 0; semantic validator (unique frame ids, refs exist, a != b, trust matches dlambda_frac thresholds, source_url rules real vs synthetic).

neptune-dial offset_px metric changed by Data to distance from pred(d) to Neptune's measured centroid (matches docs/dial_table_neptune.csv); brightest-peak criterion gave a false minimum at 36.79 AU. Science was offline; to be confirmed Sunday morning.
