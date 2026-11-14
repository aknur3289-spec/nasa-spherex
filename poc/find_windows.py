#!/usr/bin/env python
"""Find daily SPHEREx solar-elongation windows for Neptune and Uranus."""
import csv
from datetime import date, timedelta
from pathlib import Path

from astropy.time import Time

from spx.horizons import ephem
from spx.geometry import solar_elongation_deg


OUT = Path(__file__).resolve().parent
START, END = date(2025, 4, 1), date(2026, 11, 14)


def run(body: str) -> list[dict]:
    days = []
    d = START
    while d <= END:
        days.append(d.isoformat())
        d += timedelta(days=1)
    rows = ephem(body, days)
    if rows:
        print(f"{body}: ephemeris source used: {rows[0]['source']}")
    for row in rows:
        if row["elong_deg"] is None:
            row["elong_deg"] = solar_elongation_deg(
                row["ra_deg"], row["dec_deg"], Time(row["jd_utc"], format="jd", scale="utc")
            )

    selected = [i for i, row in enumerate(rows) if 85.0 <= row["elong_deg"] <= 95.0]
    groups: list[list[int]] = []
    for i in selected:
        if not groups or i != groups[-1][-1] + 1:
            groups.append([i])
        else:
            groups[-1].append(i)

    windows = []
    for number, group in enumerate(groups, 1):
        mid = rows[group[len(group) // 2]]
        windows.append({
            "window_id": number,
            "start_utc": days[group[0]],
            "end_utc": days[group[-1]],
            "mid_utc": days[group[len(group) // 2]],
            "ra_deg": mid["ra_deg"],
            "dec_deg": mid["dec_deg"],
            "r_au": mid["r_au"],
            "delta_au": mid["delta_au"],
        })
    path = OUT / f"windows_{body}.csv"
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["window_id", "start_utc", "end_utc", "mid_utc", "ra_deg", "dec_deg", "r_au", "delta_au"])
        writer.writeheader()
        writer.writerows(windows)
    print(f"{body}: wrote {len(windows)} windows to {path}")
    return windows


if __name__ == "__main__":
    for target in ("neptune", "uranus"):
        run(target)
