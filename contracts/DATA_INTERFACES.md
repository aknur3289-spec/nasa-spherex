# Data interfaces

## Dev3 decisions for v1.1 — 2026-11-14

The proposal file was unavailable in the checkout. These decisions cover the proposals supplied in the Dev3 handoff.

### Version compatibility — ACCEPT WITH CHANGES

Existing v1.0 fields remain valid. The sole required addition applies only to files that opt into v1.1.

```json
{ "schema_version": "1.1" }
```

This is a field.json fragment. Both "1.0" and "1.1" are supported; v1.0 keeps its existing required keys.

### kind — ACCEPT WITH CHANGES

Keep the producer enum closed until a new kind has a defined viewer fallback.

```json
{ "kind": "static" }
```

The only valid published values in field.json and index.json are "static" and "dial". No new value is approved. Future kinds must define an unknown-kind-to-static rendering fallback before acceptance. The v1.0/v1.1 validator rejects out-of-enum producers.

### diff_png — ACCEPT WITH CHANGES

A difference image belongs to a pair because both frames contribute pixels.

```json
{ "a": "epoch-1", "b": "epoch-2", "dlambda_frac": 0.008, "dt_days": 183, "trust": "high", "diff_png": "diff/epoch-1-epoch-2.png" }
```

Optional v1.1 pair key. The path is relative to the field directory, passes safeAsset and ends in .png. The PNG IHDR dimensions must match both frames. A declared file must exist. When omitted, the client should compute absolute pixel differences |A−B| on canvas. That rendering behavior is a UI integration follow-up.

### timeline.json — ACCEPT WITH CHANGES

A separate optional file keeps existing fields valid and offers a deterministic chronological view.

```json
[
  { "frame_id": "epoch-1", "obs_time_utc": "2030-01-01T00:00:00Z", "mjd": 62502 },
  { "frame_id": "epoch-2", "obs_time_utc": "2030-07-03T00:00:00Z", "mjd": 62685 }
]
```

Place timeline.json next to field.json for v1.1. List each field frame exactly once in ascending UTC order; ties are allowed. Each ID must exist in field.json and its timestamp and MJD must match the frame. A missing file (HTTP 404) falls back to sorting field.frames by obs_time_utc.

### index.json metadata — ACCEPT WITH CHANGES

Optional summary fields let readers show catalog metadata without opening every field.

```json
[
  {
    "field_id": "fixture-static",
    "kind": "static",
    "title": "Static star field",
    "thumbnail": "epoch-1.png",
    "thumbnail_px": { "width": 99, "height": 99 },
    "n_frames": 3,
    "date_range": { "start_utc": "2030-01-01T00:00:00Z", "end_utc": "2030-08-01T00:00:00Z" },
    "status": "ready",
    "synthetic": true
  }
]
```

All five new keys are optional. Dimensions are positive integers up to the PNG limit (2³¹−1); n_frames is a nonnegative integer; date_range uses ordered UTC timestamps; status is "ready" or "pending"; synthetic is a boolean matching field provenance when supplied. Unknown keys are ignored.

### Frame pixel dimensions — ACCEPT WITH CHANGES

Explicit dimensions let v1.1 validate the pixel grid used for pair differences.

```json
{ "id": "epoch-1", "png": "epoch-1.png", "width_px": 99, "height_px": 99 }
```

This is a frame fragment. Both dimensions are required in v1.1 and optional in v1.0. They describe the source PNG and are positive integers up to 2³¹−1. All v1.1 frames in a field share the same dimensions. Frames are typically about 99×99 px. The client should use nearest-neighbour upscaling. That rendering behavior is a UI integration follow-up.

### Open questions for Science

- [ ] Confirm the approved field list and detector assignments. Owner: ____
- [ ] Confirm ETA for predict_radec. Owner: ____
