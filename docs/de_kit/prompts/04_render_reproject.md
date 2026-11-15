# P04 — `pipeline/spx/render.py`: common grid + PNG + difference images
Tool: Codex. Branch: `data/render`. Parallel with P03 (needs only frame.py API).

---
Read AGENTS.md. Implement reprojection of every frame of a field onto ONE common grid and rendering to web PNGs with a stretch that is comparable between the two frames of a pair.

FILES
- `pipeline/spx/render.py`, `pipeline/tests/test_render.py`

API
```python
def field_grid(ra_deg, dec_deg, size_arcmin, pixel_arcsec=6.15) -> tuple[WCS, tuple[int, int]]
    # north-up TAN, odd number of pixels so the target sits on the central pixel
def to_grid(frame: Frame, grid_wcs: WCS, shape) -> tuple[np.ndarray, np.ndarray]
    # image via reproject_interp (bilinear); bad mask reprojected as float, bad = value > 0.1 or NaN
def stretch_params(images: list[np.ndarray], lo_pct=5.0, hi_pct=99.7) -> dict
    # computed on the background-subtracted (median) finite pixels of ALL given images together
def to_png(img: np.ndarray, bad: np.ndarray, stretch: dict, out: Path, scale: int = 1) -> dict
    # asinh stretch, 8-bit grayscale + alpha (bad = transparent); returns the "stretch" block:
    # {"kind": "asinh", "lo": .., "hi": .., "unit": "MJy/sr"}
def diff_png(a: np.ndarray, b: np.ndarray, bad: np.ndarray, out: Path, noise: float) -> dict
    # (a - s*b)/noise with s = median ratio over bright pixels, symmetric limits ±5σ, diverging grey map
```

RULES
- Stretch groups: ONE stretch per (field, detector) computed from all frames of that detector, so both frames of every honest pair use the same mapping (pairs are always same-detector). Record the same stretch block in every frame of the group.
- Before stretching subtract each frame's own median (zodi residual differs between seasons) — store `median_subtracted_mjysr` in the returned dict.
- PNGs are small (10′ ≈ 99 px). Write native resolution; the client will upscale with `image-rendering: pixelated`. Optional `scale` for thumbnails (nearest-neighbour).
- PNG must be deterministic for the same input (no timestamps in metadata).
- NaN-safe everywhere; an all-NaN frame raises a clear error that the caller can log and skip.

TESTS: grid is odd-sized and centred; a point source injected in a synthetic Frame with rotated WCS lands on the expected grid pixel after reprojection (±1 px); stretch shared within group; bad pixels transparent (alpha 0); diff of identical images ≈ 0.

DONE: pytest green; a demo call renders the P00 cutout to `data/meta/discovery/sample.png` that opens and looks like sky.
