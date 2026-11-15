# P01 — `pipeline/spx/io.py`: search + cached cutout download + epochs.csv (raw)
Tool: Codex (well-specified module + tests). Branch: `data/io`. Needs: P00 done (docs/DATA.md).

---
Read AGENTS.md and docs/DATA.md (real column names from discovery). Implement the ONLY module in the pipeline that talks to the network for SPHEREx.

FILES (create/modify only these)
- `pipeline/spx/__init__.py`, `pipeline/spx/io.py`
- `pipeline/fetch_field.py` (thin CLI)
- `pipeline/tests/test_io.py`

API (keep these signatures)
```python
def search_frames(ra_deg: float, dec_deg: float, detectors: list[int] | None = None,
                  collections: tuple[str, ...] = ("spherex_dr1", "spherex_qr3"),
                  mjd_range: tuple[float, float] | None = None, method: str = "tap") -> list[dict]
    # one dict per exposure: file_url, uri, collection, mjd, detector, bandpassname, planeid (+ obs_id if available)
def cutout_url(file_url: str, ra_deg: float, dec_deg: float, size_deg: float) -> str
def fetch_cutout(row: dict, ra_deg: float, dec_deg: float, size_deg: float,
                 outdir: Path = Path("data/raw")) -> Path | None
def fetch_field(field_id: str, ra_deg: float, dec_deg: float, size_deg: float,
                detectors: list[int] | None, max_workers: int = 6, limit: int | None = None) -> Path
    # returns path to data/meta/<field_id>/raw_index.csv
```

BEHAVIOUR
- TAP is the primary method (query from AGENTS.md, filter `energy_bandpassname IN ('SPHEREx-D1',...)` for requested detectors). `method="sia"` is the fallback using `Irsa.query_sia` and `access_url`.
- `collection` derived from the uri path (`/dr1/` or `/qr3/`). Deduplicate the same exposure appearing twice (same OBSID+detector, or same file basename): keep DR1 over QR3 only if processing versions are equal, otherwise keep the newer processing version; log what was dropped.
- Local filename is deterministic: `data/raw/<field_id>/<basename-without-.fits>__c{ra:.5f}_{dec:+.5f}_s{size:.4f}.fits`. If it exists and opens as FITS → skip (cache hit). Download to `*.part`, then rename (atomic).
- After download, write a slim copy WITHOUT the EPSF/PSF HDU (keep primary, IMAGE, FLAGS, VARIANCE, ZODI, WCS-WAVE) and delete the fat one, to save disk. Keep HDU names unchanged.
- Validate: opens, has IMAGE and WCS-WAVE, image area ≥ 80% of expected (size_deg*3600/6.15)^2 px and target pixel inside the image; else mark `status=partial` / `outside` and keep the row (do not delete the file).
- Retries: 3 attempts, backoff 5/15/30 s on TimeoutError, HTTPError 5xx, IncompleteRead, RemoteDisconnected, ConnectionError. HTTP 4xx → no retry, status=error.
- Parallel with ThreadPoolExecutor(max_workers ≤ 8), plus a progress line every 10 files (done/total, MB, ETA).
- `raw_index.csv` columns: field_id, file_url, source_url (= cutout url), collection, mjd, detector, bandpassname, planeid, obs_id, local_path, bytes, status (ok|cached|partial|outside|error), error, downloaded_utc, sha256.
- `limit`: take frames spread evenly in time (not the first N) — important so all survey passes are represented.

CLI
`python pipeline/fetch_field.py --id m101 --ra 210.80227 --dec 54.34895 --size-arcmin 10 --detectors 1 2 3 --workers 6 [--limit 200] [--method tap|sia]`
Prints: rows found per detector and per collection, MJD span, downloaded / cached / failed, total MB, wall time.

TESTS (offline; mock network)
- cutout_url formatting; deterministic filename; cache hit performs zero downloads (monkeypatch the downloader and count calls); dedup rule; `limit` keeps time spread; partial-area detection on a synthetic FITS you create in tmp_path.

EXCLUSIONS: no wavelength/flags/pairs/rendering logic here (that is frame.py / pairs.py). No hard-coded results.

DONE: pytest green; the M101 CLI runs once for real, prints counts; second run prints `downloaded=0`.
