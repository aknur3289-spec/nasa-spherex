"""Fetch SPHEREx cutouts for one field."""

from __future__ import annotations

import argparse

from spx.io import fetch_field


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", required=True)
    parser.add_argument("--ra", type=float, required=True)
    parser.add_argument("--dec", type=float, required=True)
    parser.add_argument("--size-arcmin", type=float, required=True)
    parser.add_argument("--detectors", nargs="+", type=int)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--method", choices=("tap", "sia"), default="tap")
    args = parser.parse_args()
    path = fetch_field(args.id, args.ra, args.dec, args.size_arcmin / 60,
                       args.detectors, args.workers, args.limit, method=args.method)
    print(path)


if __name__ == "__main__":
    main()
