# PARALLAX — Planet X × SPHEREx

NASA Space Apps Challenge 2026 · challenge "Planet X and SPHEREx".

A hidden planet would show up as one faint dot that moves between NASA SPHEREx images taken months apart,
lost among stars, detector artefacts and colour changes. PARALLAX is an open pipeline and a web tool that
finds dots that really move, rejects the fakes, and measures how far away they are.

**Blind test on real SPHEREx data.** Without being told where Neptune is, the pipeline found it in 64 of 74
image differences, kept it as the only real moving track, and measured **29.93 AU** from those detections
alone. JPL Horizons (29.89 AU) was used only to grade the answer: error 0.13 %. Details and limits:
[docs/BLIND_TEST.md](docs/BLIND_TEST.md).

## What is in the site

- **Parallax Lab** — a live parallax simulator, a hide-the-planet game, and the Neptune blind test on real
  data, computed in the browser with the same model as the pipeline.
- **Compare** — Honest Blink: only image pairs taken at (almost) the same wavelength, each with a trust badge.
- **Timelapse / Sky Explorer / any point** — real SPHEREx images of any sky position, loaded from NASA IRSA.
- **Methodology** — method, blind test, limitations, data sources.
- **Help review** — volunteers sort detector candidates into real movers and artefacts, ranked by a
  real/bogus ML model; practice round, one-key answers, exportable labels. See [docs/ML.md](docs/ML.md).

## How it works

```text
NASA IRSA SPHEREx L2 FITS → offline Python pipeline (pipeline/, poc/) → static PNG + JSON → React site (web/)
```

1. Difference images: science minus a same-sky reference from another time, reprojected, noise from VARIANCE.
2. Detection of new sources; SPHEREx `OUTLIER`/`TRANSIENT` flags are kept because they mark moving objects.
3. Linking into tracks; static sources, optical ghosts and glare companions are rejected.
4. Distance from two seasons with a circular-orbit parallax model.

Limits: the Neptune cutouts were downloaded around its position; Neptune's orbit is near-circular; a
Planet-Nine-like object is far below one image's depth and needs Shift & Stack (next step).

## Run

Web (Node.js ≥ 22.12):

```sh
npm --prefix web ci
npm --prefix web run dev      # local site
npm --prefix web test
npm --prefix web run build
```

Python tests (pipeline + ML, offline): `python3 -m pytest`

Blind test (Python, offline, needs the cached FITS in `data/raw/`):

```sh
python3 poc/blind_mover.py
python3 poc/blind_mover_tests.py
```

Data contract: [docs/CONTRACT.md](docs/CONTRACT.md) · data notes: [docs/DATA.md](docs/DATA.md) ·
decisions: [docs/DECISIONS.md](docs/DECISIONS.md) · AI use: [docs/AI_USE.md](docs/AI_USE.md).

Vercel builds `web/` and publishes `web/dist/` on every push to `main`.

Data: NASA SPHEREx via NASA/IPAC IRSA · ephemerides for grading: JPL Horizons.
