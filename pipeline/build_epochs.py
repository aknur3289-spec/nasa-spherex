"""Build offline epoch metadata from cached SPHEREx cutouts."""

import argparse
import csv
import statistics
from collections import defaultdict

from spx.frame import build_epochs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--ra", type=float, required=True)
    parser.add_argument("--dec", type=float, required=True)
    args = parser.parse_args()
    path = build_epochs(args.id, args.ra, args.dec)
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    by_detector = defaultdict(list)
    for row in rows:
        by_detector[row["detector"]].append(row)
    print(f"epochs: {len(rows)}")
    for detector, group in sorted(by_detector.items()):
        wavelengths = [float(row["wavelength_um"]) for row in group if row["wavelength_um"]]
        span = f"{min(wavelengths):.6f}–{max(wavelengths):.6f} um" if wavelengths else "n/a"
        print(f"D{detector}: {len(group)} frames; wavelength {span}")
    fractions = [float(row["bad_pixel_fraction"]) for row in rows if row["bad_pixel_fraction"]]
    print(f"median bad fraction: {statistics.median(fractions):.6f}" if fractions else "median bad fraction: n/a")
    print(f"status != ok: {sum(row['status'] != 'ok' for row in rows)}")
    print(path)


if __name__ == "__main__":
    main()
