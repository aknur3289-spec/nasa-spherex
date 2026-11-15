# Frontend data handoff

Read `web/public/data/index.json`, then each real field's `field.json`. The `demo` field is synthetic and is not part of the real gallery. All three real fields are `kind: static` (schema 1.1); none is a Distance Dial field.

| Field | Frames | Pair trust: high / medium / low | PNG size |
| --- | ---: | ---: | --- |
| `m101` | 32 | 12 / 0 / 6 | 99 × 99 px |
| `nep` | 31 | 10 / 2 / 6 | 99 × 99 px |
| `ecl` | 30 | 12 / 0 / 6 | 99 × 99 px |

No field has zero high-trust (≤2% wavelength difference) pairs. Low-trust pairs are included for comparison; show their trust badge rather than calling them wavelength-matched. Upscale the 99 × 99 frame PNGs with `image-rendering: pixelated`.

Each field also has a 198 × 198 `thumb.png`, `timeline.json`, and 18 pair differences at `diff/<a>-<b>.png`, referenced by `pairs[].diff_png`. The published `docs/CONTRACT.md` describes only frame PNGs and does not name these extras; `docs/DECISIONS.md` accepts `diff_png` and `timeline.json` for schema 1.1. `thumb.png` is referenced by `index.json`, not by each `field.json`.

## Copy the designer may use

**M101:** This field is centred on the Pinwheel Galaxy. SPHEREx frames here span May 2025 to June 2026. Choose a high-trust pair to compare views taken at nearly the same wavelength.

**North Ecliptic Pole:** This field shows the sky near the north ecliptic pole. Its published frames span May 2025 to September 2026. Some pairs differ more in wavelength, so the trust badge matters when blinking them.

**Ecliptic test field:** This is a patch of sky near the ecliptic. Its published frames span July 2025 to July 2026. The pairs show repeat views of the same field, with wavelength agreement indicated by their trust badges.
