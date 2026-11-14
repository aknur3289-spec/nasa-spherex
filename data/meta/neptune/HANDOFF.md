# Neptune data handoff

Ephemerides in `raw_index.csv` are Horizons geocentric truth at each exposure MJD.
Window 1 is June–early July 2025; window 2 is December 2025; window 3 is June–early July 2026.
Wavelength is from WCS-WAVE at the cutout centre. BAD and SAT fractions use the central 5×5 FLAGS pixels.
Templates are centred on each December science exposure's Neptune sky position, using June 2026 frames.

| Window | Catalog | Ready |
| --- | ---: | ---: |
| 1 | 54 | 54 |
| 2 | 20 | 20 |
| 3 | 0 | 0 |

Template links: 57. Failed/pending science cutouts: 0.
Paths: `epochs.csv`, `passes.json`, `templates.csv`, `templates/`, and `../neptune_cutouts.zip`.
FITS cutouts and ZIP stay outside Git; only the CSV, JSON, and this handoff are committed.
