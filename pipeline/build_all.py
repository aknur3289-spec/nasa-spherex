"""Build all enabled static fields, continuing past individual failures."""

import argparse
import sys
from pathlib import Path

import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.build_field import CONFIG_PATH, build_field


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--max-frames", type=int)
    args = parser.parse_args()
    config = yaml.safe_load(CONFIG_PATH.read_text())
    failures = 0
    print("field | result | frames | pairs")
    for field in config["fields"]:
        if not field.get("enabled", False):
            continue
        try:
            built = build_field(field["id"], offline=args.offline, max_frames=args.max_frames)
            print(f"{field['id']} | ok | {len(built['frames'])} | {len(built['pairs'])}")
        except Exception as exc:
            failures += 1
            print(f"{field['id']} | ERROR | 0 | 0: {exc}", file=sys.stderr)
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
