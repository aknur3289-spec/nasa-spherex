# Science module (Participant 1)

Copy `pipeline/` and `docs/` into the team repo (same paths). Then:

    pip install astropy astroquery numpy pytest
    pytest -q pipeline/tests                       # 6 tests, must pass
    python pipeline/validate_geometry.py           # Neptune/Uranus/Saturn distance recovery
    python pipeline/make_synthetic_dial.py         # focus curve on synthetic data + UI fixture
    cd docs && python ../pipeline/spx/detectability.py   # limits.json for the Detectability panel

Files: spx/geometry.py (predict_radec), spx/focus.py (focus_curve, dial_grid),
spx/detectability.py, spx/horizons.py (JPL Horizons, astropy fallback).
Results log: docs/EXPERIMENTS.md. Remaining work + Codex prompts: CODEX_PROMPTS.md.
