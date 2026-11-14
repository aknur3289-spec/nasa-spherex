# Static field contract 1.0

## FROZEN 2026-11-14 14:00 — changes only via v1.1 (additive) or v2 (breaking)

The offline pipeline writes `web/public/data/index.json` and one directory per field. Each field directory contains `field.json`, PNGs and optional FITS files. All asset paths are relative to that field directory. The application uses the Vite base URL for the index and never substitutes demo data for unavailable observations.

| Object | Required keys |
| --- | --- |
| Index entry | `field_id`, `kind`, `title`, `thumbnail` |
| Field | `schema_version` (string `"1.0"`), `field_id`, `kind`, `title`, `description`, `center`, `size_arcmin`, `pixel_scale_arcsec`, `frames`, `pairs`, `provenance` |
| Frame | `id`, `png`, `obs_time_utc`, `mjd`, `survey_pass`, `detector`, `wavelength_um`, `center`, `bad_pixel_fraction`, `stretch`, `source_url`, `obs_id`, `processing_version` |
| Pair | `a`, `b`, `dlambda_frac`, `dt_days`, `trust` |
| Stretch | `kind` (`asinh`), `lo`, `hi`, `unit` |
| Provenance | `mission`, `archive`, `collections`, `doi`, `downloaded_utc`, `pipeline_commit`, `cached`, `synthetic` |
| Dial | `reference_frame`, `model`, `search_radius_px`, `steps`, `peak_distance_au`, `truth`, `negative_control_field`; optional (v1.1) `ref_obs_id`, `target_obs_id`, `truth_au`, `measured_au`, `note` |
| Dial step | `distance_au`, `frame`, `pred`, `snr`, `offset_px`; optional (v1.1) `outside_frame` |

The index is an array. Field and frame IDs use lowercase ASCII letters and digits with optional single hyphen or underscore separators. IDs are unique within their lists. A field ID must match its directory name. Asset paths use ASCII letters, digits, underscores, hyphens and slash separators. Absolute paths, traversal, percent escapes and URL suffixes are invalid. PNGs are required. Frames may include a relative `fits` path and a `band` string. The viewer displays the detector number if band is absent.

Coordinates have numeric `ra_deg` in [0, 360) and `dec_deg` in [-90, 90]. Dates are ISO 8601 timestamps ending in Z. Wavelength, size and pixel scale are positive in the units in their key names. Survey pass and detector are nonnegative integers. Bad pixel fraction is in [0, 1]. MJD and numeric stretch bounds must be finite. Stretch lo must be below hi.

Pair endpoints are distinct frame IDs in the same field. Time separation and fractional wavelength difference are nonnegative. Trust is high at or below 0.02, medium above 0.02 through 0.05, and low above 0.05. The loader rejects inconsistent trust.

Field kind is `static` or `dial`. Dial data is required for dial fields. Dial references and step frames must exist in the field. Step predictions are coordinates. Truth has positive `distance_au` and a nonempty `source`. A step with `outside_frame: true` means the predicted position falls off the detector: its `frame`, `snr` and `offset_px` must be `null`, and the viewer shows "Outside the frame" instead of an image and leaves a gap in the curve. At least one step must be inside a frame. The basic viewer does not render dial metadata.

Real frames include an HTTPS URL for the original IRSA product or catalog record. Fixture frames use `https://example.invalid/` and set `provenance.synthetic` to true. `cached` and `synthetic` are booleans and collections is a nonempty array of strings. The app displays DEMO DATA for synthetic fields.

See [the complete demo](../web/public/data/fixture-static/field.json) and [TypeScript definitions](../web/src/contract.ts). Additive changes bump the minor version. Breaking changes require Dev3 approval, a new major version, and an entry in docs/DECISIONS.md.
