#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from citylore_utils import build_exports, find_repo_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild CityLore machine-facing exports.")
    parser.add_argument("--repo-root", help="Override CityLore repo root.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path(__file__))
    result = build_exports(repo_root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Rebuilt catalog: {result['catalog_path']}")
        print(f"Rebuilt places export: {result['places_path']}")
        print(f"Rebuilt opinions export: {result['opinions_path']}")
        print(f"Places: {result['place_count']} | Opinions: {result['opinion_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

