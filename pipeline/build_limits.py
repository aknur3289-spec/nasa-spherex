"""Build the SPHEREx detectability data and slide figure."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import FixedLocator, FixedFormatter
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from spx.detectability import (  # noqa: E402
    PRESETS,
    SINGLE_FRAME_LIMIT_AB,
    H_from_size,
    apparent_mag,
    limit_mag,
    max_distance_au,
)

OUT_JSON = ROOT / "out" / "limits.json"
FIG_DIR = ROOT / "docs" / "figures"
CAVEATS = [
    "V magnitude used as a proxy for near-IR AB",
    "methane absorption and phase effects ignored; real limits are worse",
    "single-frame limit AB 18.4 (5 sigma) is from a secondary source",
]


def build() -> dict:
    distances = np.geomspace(20, 1500, 60)
    ns = (1, 4, 100, 300)
    data = {
        "schema": "limits-1.0",
        "model": "reflected light, r≈Δ≈d, phase ignored",
        "caveats": CAVEATS,
        "single_frame_limit_ab": SINGLE_FRAME_LIMIT_AB,
        "limits": {str(n): round(float(limit_mag(n)), 2) for n in ns},
        "distances_au": [round(float(d), 6) for d in distances],
        "bodies": [],
        "planet_nine_literature": {"V_range": [21.9, 22.7], "source": "arXiv 2507.22297"},
    }
    for name, (diameter, albedo) in PRESETS.items():
        data["bodies"].append({
            "name": name,
            "diameter_km": diameter,
            "albedo": albedo,
            "H": round(float(H_from_size(diameter, albedo)), 4),
            "mag": [round(float(m), 4) for m in apparent_mag(diameter, albedo, distances)],
            "max_d_au": {str(n): round(float(max_distance_au(diameter, albedo, n)), 2) for n in (1, 100, 300)},
        })
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    make_figure(data)
    return data


def make_figure(data: dict) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(13.5, 7.6), facecolor="white")
    ax.set_facecolor("white")
    colors = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9"]
    x = data["distances_au"]
    for body, color in zip(data["bodies"], colors):
        ax.plot(x, body["mag"], label=body["name"], color=color, linewidth=2.7)
    label_offsets = {1: 0.0, 100: -0.42, 300: 0.42}
    for n, color in ((1, "#333333"), (100, "#666666"), (300, "#999999")):
        y = data["limits"][str(n)]
        ax.axhline(y, color=color, linestyle="--", linewidth=1.8)
        ax.text(0.015, y + label_offsets[n], f"N={n}: AB {y:.1f}", color=color,
                transform=ax.get_yaxis_transform(), ha="left", va="center", fontsize=13,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85, "pad": 2})
    lo, hi = data["planet_nine_literature"]["V_range"]
    ax.add_patch(Rectangle((290, lo), 510, hi - lo, facecolor="#F0E442",
                           edgecolor="none", alpha=0.32, zorder=0))
    ax.text(545, (lo + hi) / 2, "Planet Nine (predicted)", ha="center", va="center",
            fontsize=14, color="#514800",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.78, "pad": 2}, zorder=4)
    ax.scatter([30], [7.8], s=95, marker="*", color="#000000", edgecolor="white",
               linewidth=0.8, zorder=5, label="Neptune today")
    ax.annotate("Neptune today", (30, 7.8), xytext=(12, 12), textcoords="offset points",
                fontsize=13, ha="left", va="bottom")
    ax.set_xscale("log")
    ax.set_xlim(20, 1500)
    ax.set_ylim(27, 5)
    x_ticks = [20, 50, 100, 200, 500, 1000]
    ax.xaxis.set_major_locator(FixedLocator(x_ticks))
    ax.xaxis.set_major_formatter(FixedFormatter([str(t) for t in x_ticks]))
    ax.set_xlabel("Distance (AU)", fontsize=18, labelpad=10)
    ax.set_ylabel("Apparent magnitude (V ≈ near-IR AB)", fontsize=18, labelpad=10)
    ax.tick_params(axis="both", labelsize=14)
    ax.grid(True, which="major", color="#dddddd", linewidth=0.8)
    ax.grid(True, which="minor", color="#eeeeee", linewidth=0.5)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2,
              fontsize=12, frameon=False, handlelength=2.5, columnspacing=1.5)
    fig.subplots_adjust(bottom=0.28, left=0.12, right=0.98, top=0.98)
    fig.savefig(FIG_DIR / "detectability.png", dpi=200, facecolor="white", bbox_inches="tight")
    fig.savefig(FIG_DIR / "detectability.svg", facecolor="white", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    result = build()
    print("max_d_au (AU)")
    print(f"{'Body':48} {'N=1':>8} {'N=100':>8} {'N=300':>8}")
    for body in result["bodies"]:
        limits = body["max_d_au"]
        print(f"{body['name']:48} {limits['1']:8.2f} {limits['100']:8.2f} {limits['300']:8.2f}")
