"""Real/bogus classifier for blind moving-object candidates.

A candidate is one detection in one difference image (science minus same-sky reference), as
produced by `poc/blind_mover.py`. The classifier gives each candidate a probability of being a
real astrophysical point source that is new in the science frame (a mover), rather than an
artefact: static-star residual, cosmic ray / hot pixel, optical ghost, edge effect.

Pipeline
  features.py  numbers and image stamps measured around one candidate
  synthetic.py labelled synthetic scenes run through the real blind detector (tests, demo)
  dataset.py   labelled candidates from real SPHEREx data (needs the cached FITS in data/raw)
  train.py     gradient-boosted trees, grouped cross-validation, metrics, saved model
  export_review.py  ranked queue + stamps for the volunteer Review page (web/public/data/review)
"""
