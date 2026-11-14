"""Create three slide-ready figures for the distance-recovery pitch."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from astropy.time import Time
from matplotlib.patches import Arc

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "figures"
PALETTE = {"ink": "#222B38", "blue": "#0072B2", "orange": "#D55E00",
           "green": "#009E73", "sky": "#56B4E9", "gray": "#65717E"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 16,
                     "axes.labelsize": 17, "xtick.labelsize": 15,
                     "ytick.labelsize": 15, "legend.fontsize": 15,
                     "svg.fonttype": "none"})


def save(fig: plt.Figure, stem: str) -> None:
    fig.savefig(OUT / f"{stem}.png", dpi=200, facecolor="white", bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.svg", facecolor="white", bbox_inches="tight")
    plt.close(fig)


def parallax_explainer() -> None:
    fig, ax = plt.subplots(figsize=(12, 6.75))
    ax.set_aspect("equal")
    ax.axis("off")
    # Schematic distances are intentionally exaggerated for clarity.
    earth_r, body_r = 1.65, 4.25
    ax.add_patch(plt.Circle((0, 0), earth_r, fill=False, lw=2.2, color=PALETTE["blue"]))
    ax.add_patch(plt.Circle((0, 0), body_r, fill=False, lw=1.7, color="#AEB8C2", ls=(0, (4, 4))))
    ax.scatter([0], [0], s=260, color="#E69F00", edgecolor="white", linewidth=1.5, zorder=5)
    ax.text(0.16, -0.3, "Sun", fontsize=17, color=PALETTE["ink"])
    ax.text(-3.25, 1.85, "Earth's orbit · 1 AU", ha="left", color=PALETTE["blue"])
    # Earth at opposing points, with corresponding body positions a little apart along its orbit.
    e_june, e_dec = np.array([-earth_r, 0.0]), np.array([earth_r, 0.0])
    b_june = body_r * np.array([np.cos(np.deg2rad(32)), np.sin(np.deg2rad(32))])
    b_dec = body_r * np.array([np.cos(np.deg2rad(39)), np.sin(np.deg2rad(39))])
    ax.scatter(*e_june, s=190, color=PALETTE["blue"], edgecolor="white", linewidth=1.5, zorder=5)
    ax.scatter(*e_dec, s=190, color=PALETTE["sky"], edgecolor="white", linewidth=1.5, zorder=5)
    ax.text(-3.25, -0.12, "June 2025", ha="right", va="center", color=PALETTE["ink"])
    ax.text(3.25, -0.12, "December 2025", ha="left", va="center", color=PALETTE["ink"])
    baseline_y = -1.95
    ax.plot([e_june[0], e_june[0]], [0, baseline_y], color=PALETTE["gray"], lw=1.0)
    ax.plot([e_dec[0], e_dec[0]], [0, baseline_y], color=PALETTE["gray"], lw=1.0)
    ax.annotate("", xy=(e_dec[0], baseline_y), xytext=(e_june[0], baseline_y),
                arrowprops={"arrowstyle": "<->", "color": PALETTE["gray"], "lw": 1.4})
    ax.text(0, baseline_y - .18, "baseline ≈ 2 AU", ha="center", va="top",
            fontsize=14, color=PALETTE["gray"])
    for e, b, color in ((e_june, b_june, PALETTE["blue"]), (e_dec, b_dec, PALETTE["sky"])):
        ax.plot([e[0], b[0]], [e[1], b[1]], color=color, lw=2, alpha=.85, zorder=1)
        ax.scatter(*b, s=170, marker="D", color=PALETTE["orange"], edgecolor="white", linewidth=1.4, zorder=6)
    # Short orbital arc and direction arrow between epochs.
    angles = np.linspace(32, 39, 50)
    ax.plot(body_r * np.cos(np.deg2rad(angles)), body_r * np.sin(np.deg2rad(angles)),
            color=PALETTE["orange"], lw=3, solid_capstyle="round")
    ax.annotate("", xy=(b_dec[0], b_dec[1]), xytext=(b_june[0], b_june[1]),
                arrowprops={"arrowstyle": "-|>", "color": PALETTE["orange"], "lw": 2})
    ax.text(3.15, 3.15, "orbital motion", color=PALETTE["orange"], ha="center")
    body_mid = (b_june + b_dec) / 2
    sight_angles = sorted(np.degrees(np.arctan2(e[1] - body_mid[1], e[0] - body_mid[0]))
                          for e in (e_june, e_dec))
    ax.add_patch(Arc(body_mid, .62, .62, theta1=sight_angles[0], theta2=sight_angles[1],
                     color=PALETTE["ink"], lw=1.6, zorder=7))
    ax.annotate("parallax angle", xy=body_mid + np.array([-.28, -.18]),
                xytext=(5.0, 1.45), ha="right", va="center", fontsize=15,
                color=PALETTE["ink"], arrowprops={"arrowstyle": "->", "lw": 1.2,
                                                 "color": PALETTE["gray"]})
    d_end = body_mid
    ax.plot([0, d_end[0]], [0, d_end[1]], color=PALETTE["gray"], lw=1.3,
            ls=(0, (4, 4)), zorder=0)
    d_mid = d_end * .53
    ax.text(d_mid[0] - .06, d_mid[1] + .3, "d (distance)", rotation=35,
            ha="center", va="bottom", fontsize=15, color=PALETTE["gray"],
            rotation_mode="anchor")
    ax.text(.99, .04, "Not to scale", transform=ax.transAxes, ha="right", va="bottom",
            fontsize=12, color=PALETTE["gray"])
    ax.set_xlim(-5.4, 5.4); ax.set_ylim(-2.6, 5.2)
    fig.subplots_adjust(left=.04, right=.96, top=.96, bottom=.04)
    save(fig, "parallax_explainer")


def distance_recovery() -> None:
    rows = json.loads((ROOT / "docs" / "validation_geometry.json").read_text())
    names = [r["body"].title() for r in rows]
    values = np.array([[r["d_true_au"], r["d_fit_au"], r["d_fit_static_au"]] for r in rows])
    errors = np.array([[0.0, r["err_pct"], r["err_static_pct"]] for r in rows])
    fig, ax = plt.subplots(figsize=(12, 6.75))
    x = np.arange(len(rows)); width = .23
    series = [("True distance", 0, PALETTE["ink"]),
              ("Parallax + orbit", 1, PALETTE["blue"]),
              ("Parallax only", 2, PALETTE["orange"])]
    for label, j, color in series:
        bars = ax.bar(x + (j - 1) * width, values[:, j], width, color=color, label=label, zorder=3)
        for i, bar in enumerate(bars):
            val = errors[i, j]
            if j == 0:
                continue
            err_label = "0.0%" if abs(val) < .05 else f"{val:+.1f}%"
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + .55, err_label,
                    ha="center", va="bottom", fontsize=13, color=PALETTE["ink"])
    ax.set_ylabel("Distance (AU)")
    ax.set_xticks(x, names)
    ax.set_ylim(0, 36)
    ax.grid(axis="y", color="#D9DEE3", lw=.8, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, ncol=3, loc="upper left")
    ax.text(.99, .89, "The orbit term is required", transform=ax.transAxes, ha="right", va="top",
            fontsize=18, weight="bold", color=PALETTE["ink"])
    fig.tight_layout()
    save(fig, "distance_recovery")


def _focus_curves(field: dict) -> tuple[list[dict], list[dict]]:
    """Recompute the two curves omitted from field.json using its exact synthetic setup."""
    sys.path.insert(0, str(ROOT / "pipeline"))
    from build_dial import PIXEL_SCALE, STAMP_SIZE
    from spx.focus import focus_curve
    from spx.horizons import ephem
    from spx.stamps import SyntheticProvider

    frames = field["frames"]
    t0, t1 = Time(frames[0]["obs_time_utc"]), Time(frames[1]["obs_time_utc"])
    ra0, dec0 = frames[0]["center"]["ra_deg"], frames[0]["center"]["dec_deg"]
    e1 = ephem("Neptune", [t1])[0]
    provider = SyntheticProvider(e1["ra_deg"], e1["dec_deg"], pixel_scale_arcsec=PIXEL_SCALE,
                                 stamp_size=STAMP_SIZE)
    distances = [step["distance_au"] for step in field["dial"]["steps"]]
    parallax = focus_curve(ra0, dec0, t0, t1, distances, provider.get_diff_stamp, orbit="static")
    provider.body_ra_deg, provider.body_dec_deg = ra0, dec0
    empty = focus_curve(ra0, dec0 + 1.0, t0, t1, distances, provider.get_diff_stamp)
    return parallax, empty


def focus_curve_figure() -> None:
    folder = ROOT / "out" / "neptune-synthetic"
    summary = json.loads((folder / "summary.json").read_text())
    field = json.loads((folder / "field.json").read_text())
    circular = field["dial"]["steps"]
    static, empty = _focus_curves(field)
    fig, ax = plt.subplots(figsize=(12, 6.75))
    lines = [("Our model (parallax + orbit)", circular, PALETTE["blue"]),
             ("Parallax only", static, PALETTE["orange"]),
             ("Empty sky", empty, PALETTE["green"])]
    for label, steps, color in lines:
        ax.plot([s["distance_au"] for s in steps], [s["snr"] for s in steps],
                lw=2.5, color=color, label=label)
    peak_labels = [
        (circular, f"{summary['runs']['circular']['peak_distance_au']:.1f} AU (model)", (-10, 16), "right"),
        (static, f"{summary['runs']['static_baseline']['peak_distance_au']:.1f} AU "
                 "(parallax only — wrong)", (8, -26), "left"),
        (empty, f"{summary['runs']['empty_sky_control']['peak_distance_au']:.1f} AU\n(empty sky)",
         (8, 30), "left"),
    ]
    for steps, label, offset, alignment in peak_labels:
        peak = max(steps, key=lambda step: step["snr"])
        ax.annotate(label, (peak["distance_au"], peak["snr"]), xytext=offset,
                    textcoords="offset points", fontsize=13, color=PALETTE["ink"],
                    ha=alignment, va="center", annotation_clip=False)
    truth = float(summary["truth_distance_au"])
    ax.axvline(truth, color=PALETTE["ink"], lw=1.8, ls=(0, (5, 4)))
    ax.annotate("Neptune, JPL 29.9 AU", xy=(truth, .78), xycoords=("data", "axes fraction"),
                xytext=(8, -4), textcoords="offset points", rotation=90, va="top", ha="left",
                color=PALETTE["ink"], fontsize=14)
    ax.set_xscale("log")
    ax.set_xticks([15, 30, 100, 300, 1000], labels=["15", "30", "100", "300", "1000"])
    ax.set_xlim(14, 1100)
    ax.set_xlabel("Assumed distance (AU)")
    ax.set_ylabel("Signal-to-noise ratio")
    ax.set_ylim(0, 300)
    ax.grid(color="#D9DEE3", lw=.8, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper right")
    ax.text(.63, .52, "Synthetic images — method demo", transform=ax.transAxes,
            ha="left", va="top", fontsize=14, color=PALETTE["gray"])
    fig.tight_layout()
    save(fig, "focus_curve_synthetic")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    parallax_explainer()
    distance_recovery()
    focus_curve_figure()


if __name__ == "__main__":
    main()
