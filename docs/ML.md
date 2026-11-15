# Real/bogus classifier and volunteer Review

The blind detector (`poc/blind_mover.py`) finds many "new" dots per image difference; most are artefacts.
`ml/` scores each detection with the probability that it is a real new point source (a mover), and
the **Help review** page (`#/review`) lets volunteers check the ranked candidates. Their answers are
exported as JSON and become new training labels.

```text
data/raw FITS ─► blind_mover.difference + detect ─► ml.features (14 numbers + 21×21 stamps)
             ─► ml.dataset (labels) ─► ml.train (model + metrics) ─► ml.export_review ─► web/public/data/review/<set>/
             ─► volunteers on #/review ─► labels JSON ─► back into training
```

## Labels on real data (`ml/dataset.py`)

| Kind | Real? | Where it comes from | Weight |
| --- | --- | --- | ---: |
| `mover` | yes | Neptune frames, candidate within 2 px of JPL Horizons | 1.0 |
| `neptune_other` | no | Neptune frames, every other candidate (ghosts, glare, star residuals) | 1.0 |
| `injected` | yes | Gaussian point sources injected into control-field science frames (5–50× noise), recovered | 1.0 |
| `control` | no (presumed) | Candidates already in control-field differences; a few may be real asteroids | 0.5 |

Horizons is used only to create labels; it is never a model input. Neptune is bright, so the faint
end of the real class comes from injections.

## Features (`ml/features.py`)

`z`, `new_flux_frac`, `support_2sig`, `sharpness`, `fwhm_px`, `ellipticity`, `psf_corr`, `neg_frac`,
`neg_pos_ratio`, `ref_peak_z`, `ref_bright_dist_px`, `bad_frac_stamp`, `edge_dist_px`, `z_ring_rms`.
Each targets one artefact type: hot pixels (sharpness, support), misregistered stars (negative lobes,
reference brightness), ghosts (FWHM), streaks (ellipticity), mask edges.

## Model and evaluation (`ml/train.py`)

scikit-learn `HistGradientBoostingClassifier`, balanced classes, sample weights from the table above.
Grouped K-fold: all detections from one exposure / image pair stay in the same fold. Reported: ROC AUC,
average precision, recall at 90 % purity, the same AUC for a `z`-only ranking (baseline), and the share
of each artefact kind pushed below 0.5.

**Real-data result (2026-11-15).** 405 candidates from the blind-test differences (67 Neptune, 90 recovered
injections, 201 other Neptune-frame candidates, 47 control-field candidates), 127 groups, grouped 5-fold CV:

| Metric | Value |
| --- | ---: |
| ROC AUC | 0.963 |
| ROC AUC, ranking by `z` only (baseline) | 0.562 |
| Average precision | 0.948 |
| Recall at 90 % purity | 0.834 |
| Neptune artefacts (`neptune_other`) scored below 0.5 | 91.0 % |
| Control-field candidates scored below 0.5 | 93.6 % |
| Neptune detections kept (≥ 0.5) | 95.5 % |
| Recovered injections kept (≥ 0.5) | 82.2 % |

Caveats: a small set; one feature (`new_flux_frac`) carries most of the model's importance; the real class
is bright Neptune plus synthetic injections, so faint real movers are represented only by injections.

Synthetic check (`python3 -m ml.train --synthetic`): AUC 0.997, z-only baseline 0.49.

## Run

```sh
pip install scikit-learn joblib            # new dependencies for ml/ only
python3 -m pytest                          # pipeline + ml tests (pytest.ini sets the paths)

# on the machine that has data/raw + data/meta from the blind test:
python3 -m ml.dataset                      # -> data/meta/ml/candidates.csv + stamps.npz
python3 -m ml.train                        # -> data/meta/ml/model.joblib + metrics.json
python3 -m ml.export_review --data data/meta/ml/candidates.csv --model data/meta/ml/model.joblib --set-id blind-v1

# synthetic practice set shown on the site today:
python3 -m ml.export_review --synthetic-demo
```

## Review page (`web/src/survey/Review.tsx`)

- Practice round of 5 known-answer items with feedback, then the ML-ranked queue (mostly most-likely-real
  first, about 25 % uncertain cases mixed in so volunteer answers improve the model where it is weakest).
- Old / New / Difference stamps with a crosshair, auto-blink, one-key answers (`1` real, `2` artefact,
  `3` not sure, `Z` undo, `Space` blink, `D` difference).
- The model's opinion is hidden until the volunteer answers, so it does not bias them (opt-in toggle).
- Answers stay in the browser (localStorage) until the volunteer downloads them (`review-labels-1.0` JSON).
- Synthetic sets carry a "PRACTICE DATA (synthetic)" banner; real sets link each candidate to the sky viewer.

Queue format `review-1.0`: `web/public/data/review/index.json` lists sets; each set has `queue.json` and
`stamps/<id>_{sci,ref,diff}.png` (21×21 px).

## Next steps

1. Done: real-data metrics above.
2. Score the five unverified `ecl` mover tracks and cross-match them with SkyBoT.
3. Add volunteer label import to `ml.dataset` (majority vote, weight by practice score).
4. A small CNN on the 21×21 stamps once there are a few thousand labels.
