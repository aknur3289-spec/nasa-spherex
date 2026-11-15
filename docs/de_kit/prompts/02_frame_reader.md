# P02 — `pipeline/spx/frame.py`: read a cutout → clean image + metadata → epochs.csv
Tool: Claude Code (needs to look at real FITS from P00). Branch: `data/frame`. Runs in parallel with P01 (use the cutout from P00 for development).

---
Read AGENTS.md and docs/DATA.md (flag_bits.json, BAD_BITS proposal, header sample). Implement offline reading of one cutout.

FILES
- `pipeline/spx/frame.py`
- `pipeline/build_epochs.py` (CLI)
- `pipeline/tests/test_frame.py`

API
```python
BAD_BITS: tuple[str, ...]   # names from docs/DATA.md; SOURCE is NOT in it
@dataclass
class Frame:
    image: np.ndarray        # float32, MJy/sr, ZODI subtracted, NaN where bad
    bad: np.ndarray          # bool mask
    variance: np.ndarray
    wcs: WCS                 # spatial
    meta: dict               # see below
def bad_mask(flags: np.ndarray, flags_header) -> np.ndarray       # bit numbers resolved from MSKN* keys by name
def wavelength_at(hdul, ra_deg, dec_deg) -> tuple[float, float, float, float]  # wl_um, bw_um, x_pix, y_pix
def read_frame(path: Path, ra_deg: float, dec_deg: float) -> Frame
def build_epochs(field_id: str, ra_deg: float, dec_deg: float) -> Path   # reads raw_index.csv, writes epochs.csv
```

meta / epochs.csv columns (one row per usable frame)
frame_id (f001… stable: sorted by mjd, then detector, then obs_id), field_id, obs_id, detector, collection, processing_version (primary VERSION), mjd, obs_time_utc (ISO Z), wavelength_um, bandwidth_um, x_pix, y_pix, bad_pixel_fraction (inside the cutout), target_bad (bool: is the target pixel or its 3×3 neighbourhood bad), zodi_median_mjysr, image_median_mjysr, noise_mad_mjysr, psf_fwhm_arcsec (if in header), survey_pass (filled by pairs.py later, leave empty), source_url, local_path, downloaded_utc, status.

RULES
- Bad mask from BAD_BITS resolved by NAME → bit via the header (do not hard-code bit numbers). If a BAD_BITS name is missing in a header, log a warning once.
- Image = IMAGE − ZODI, then bad pixels → NaN. Do not subtract a median here (render.py decides).
- Wavelength via spectral WCS key='W' with sip=None at the target pixel (world_to_pixel with the spatial WCS). Sanity check: wavelength inside the detector band from AGENTS.md, else status=bad_wavelength.
- Frames with bad_pixel_fraction > 0.30 stay in epochs.csv with status=too_many_bad (excluded from pairs later, but kept for transparency).
- Robust noise = 1.4826·MAD of finite pixels.
- Never crash the whole field on one broken file: log, status=error, continue.

CLI: `python pipeline/build_epochs.py --id m101 --ra 210.80227 --dec 54.34895` → prints N frames, per detector counts, wavelength range per detector, median bad fraction, how many with status≠ok.

TESTS: build a synthetic MEF in tmp_path with IMAGE/FLAGS(+MSKN keys)/ZODI and a simple linear WCS; check SOURCE bit is ignored; a BAD bit is masked; zodi subtracted; bad fraction correct. One test (marked `@pytest.mark.real`, skipped if file absent) on the P00 cutout: wavelength inside D2 band.

DONE: pytest green; epochs.csv for M101 written; numbers printed.
