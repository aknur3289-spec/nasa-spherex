# Blind moving-object test (Neptune as the hidden answer)

Run 2026-11-15, offline, on cached SPHEREx L2 cutouts. Code: `poc/blind_mover.py`, `poc/blind_mover_tests.py`.
Outputs: `data/meta/blind/` (git-ignored). Figure: `docs/figures/blind_test.png`.

## Question

Can the pipeline **find** a moving object and **measure its distance** without being told where it is?
Earlier Distance Dial results took Neptune's first position from JPL Horizons and searched for it around
the Horizons position in the second epoch. Here the detector, the linking and the distance fit never read
Horizons. Horizons is loaded only at the end, to grade the result.

## Method

1. **Difference image.** Science `IMAGE − ZODI` minus a reference of the same sky at another time,
   reprojected onto the science grid (`reproject_interp`), flux-scaled on bright reference pixels,
   noise from `VARIANCE` rescaled to the measured scatter. December references are the June 2026
   same-sky templates (Neptune absent). June references are other June 2025 exposures ≥ 4 days away
   (Neptune moves ~2.8 px/day), chosen by footprint overlap only. Wavelength mismatch ≤ 10 %.
2. **Detection.** Local maxima with z > 5, ≥ 3 neighbouring pixels above 2σ, and at least half of the
   peak flux absent from the reference (rejects residuals of static stars).
3. **Linking.** Candidates from different exposures are joined into the track with the most exposures
   (linear seed, quadratic refinement, 3 px tolerance). Each track is labelled:
   *static* (moves < 5 px over the window), *ghost* (fixed detector-pixel offset from a brighter mover),
   *companion* (≥ 80 % of its points in the brighter mover's exposures and within 50 px of it), or *mover*.
4. **Distance.** Circular heliocentric orbit through the June track anchor, orbit pole near the ecliptic
   pole with a free tilt, propagated to the December times; the trial distance r with the smallest RMS miss
   on the December track wins. Earth positions from Astropy's built-in ephemeris. Bootstrap (60×) over
   detections with 0.3 px centroid jitter.

## Finding about the SPHEREx flags

The SPHEREx pipeline marks a moving source's core as `OUTLIER` / `TRANSIENT` (it disagrees with the
other samples). The Honest Blink mask treats those bits as bad and removes them. For a moving-object
search they are signal. Mask ablation on the 74 Neptune differences:

| Mask | Neptune detected |
| --- | ---: |
| Honest Blink mask (OUTLIER, TRANSIENT masked) | 54 / 74 |
| Mover-aware mask (both kept) | **64 / 74** |

## Results

| | June 2025 | December 2025 |
| --- | ---: | ---: |
| Differences with a valid reference | 48 | 26 |
| Neptune detected (within 2 px of Horizons) | 40 | 24 |
| … and it is the strongest candidate | 35 | 23 |
| Best *mover* track | Neptune, 44 points | Neptune, 26 points |
| Track median offset from Horizons | 4.2″ (0.7 px) | 3.4″ (0.6 px) |
| Other tracks found | 1 static, 3 companions, 3 ghosts | 1 companion |

**Blind distance: 29.93 AU (bootstrap σ 0.02 AU). Horizons heliocentric distance at the anchor epoch:
29.89 AU. Error 0.04 AU (0.13 %).** The miss curve has one sharp minimum between 5 and 300 AU
(panel 2 of the figure).

**Control fields** (Honest Blink high-trust pairs, no known planet, same detector and linking):

| Field | Differences | Candidates | Unverified *mover* tracks |
| --- | ---: | ---: | ---: |
| m101 | 24 | 10 | 0 |
| nep | 24 | 35 | 2 |
| ecl (on the ecliptic) | 24 | 63 | 5 |

The control epochs are months apart, which makes chance alignments easier than in the Neptune
windows. Some `ecl` tracks may be real asteroids; they could not be cross-matched offline (no MPC access).

**Depth (injection–recovery).** A Gaussian point source (median FWHM 1.2 px) was injected into science
frames of the control pairs, 6 per frame, ~115 per level:

| Injected peak (× single-pixel noise) | 3 | 5 | 7 | 10 | 15 | 25 | 50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Recovered | 0 % | 3 % | 21 % | 43 % | 74 % | 86 % | 95 % |

50 % completeness is near 10× the pixel noise (~0.24 MJy/sr peak), about 500× (≈ 7 mag) fainter than
Neptune's peak in the same frames.

## What this does and does not show

- Shows: on real SPHEREx data, the pipeline finds a moving object, separates it from static residuals,
  optical ghosts and companions, links it across exposures, and recovers its distance to 0.13 % without
  using the ephemeris.
- Does not show: a search of the open sky. The cutouts were downloaded centred on Neptune's predicted
  position, so the search area was chosen with prior knowledge, even though the algorithm does not use it.
- Neptune's orbit is nearly circular (e ≈ 0.01), which favours the circular-orbit fit; eccentric objects
  will have larger distance errors.
- A Planet-Nine-like object would be far fainter than the single-exposure limit above. Reaching it needs
  Shift & Stack over many exposures; this is the next step.
- Statistical σ (0.02 AU) excludes model systematics.
