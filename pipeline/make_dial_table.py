import csv, json, sys
from pathlib import Path
import numpy as np
from astropy.time import Time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from spx.geometry import predict_radec, ang_sep_deg
PIX = 6.15
src = json.load(open(ROOT / "poc/out/astrometric_distance.json"))
ref, tgt = src["exposures"]["1"][0], src["exposures"]["2"][0]
t0 = Time(ref["mjd"], format="mjd", scale="utc")
t1 = Time(tgt["mjd"], format="mjd", scale="utc")
ra0, dec0 = ref["measured_ra_deg"], ref["measured_dec_deg"]
ra1, dec1 = tgt["measured_ra_deg"], tgt["measured_dec_deg"]
rows = []
for d in np.round(np.arange(20.0, 45.0 + 1e-9, 0.1), 1):
    row = {"distance_au": f"{d:.1f}"}
    for model, tag in (("circular", "model"), ("static", "parallax_only")):
        p = predict_radec(ra0, dec0, t0, float(d), t1, orbit=model)[0]
        miss = float(ang_sep_deg(p[0], p[1], ra1, dec1)) * 3600
        row.update({f"{tag}_pred_ra_deg": f"{p[0]:.6f}", f"{tag}_pred_dec_deg": f"{p[1]:.6f}",
                    f"{tag}_miss_arcsec": f"{miss:.1f}", f"{tag}_miss_px": f"{miss / PIX:.2f}"})
    rows.append(row)
with open(ROOT / "docs/dial_table_neptune.csv", "w", newline="") as f:
    f.write(f"# ref {ref['obs_id']} target {tgt['obs_id']} truth {src['truth_r_au']:.2f} AU\n")
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
b = min(rows, key=lambda r: float(r["model_miss_arcsec"]))
s = min(rows, key=lambda r: float(r["parallax_only_miss_arcsec"]))
print("rows", len(rows), "| model minimum at", b["distance_au"], "AU, miss", b["model_miss_arcsec"], "arcsec | parallax-only minimum at", s["distance_au"], "AU")
