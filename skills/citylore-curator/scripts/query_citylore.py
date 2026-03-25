#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from citylore_utils import build_catalog_structure, find_repo_root, haversine_km, score_text_match


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query CityLore exports or canonical data.")
    parser.add_argument("--repo-root", help="Override CityLore repo root.")
    parser.add_argument("--text", help="Free-form text search.")
    parser.add_argument("--city", help="Filter by city.")
    parser.add_argument("--district", help="Filter by district.")
    parser.add_argument("--category", help="Filter by category.")
    parser.add_argument("--contributor-id", help="Filter by contributor.")
    parser.add_argument("--tag", action="append", default=[], help="Repeatable tag filter.")
    parser.add_argument("--near-lat", type=float, help="Latitude for nearby search.")
    parser.add_argument("--near-lng", type=float, help="Longitude for nearby search.")
    parser.add_argument("--radius-km", type=float, default=5.0, help="Nearby search radius.")
    parser.add_argument("--coord-system", help="Optional coord system filter when using nearby search.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path(__file__))
    catalog = build_catalog_structure(repo_root)
    opinions_by_place: dict[str, list[dict]] = {}
    for opinion in catalog["opinions"]:
        opinions_by_place.setdefault(opinion["place_id"], []).append(opinion)

    required_tags = {item.strip() for item in args.tag if item.strip()}
    results = []
    for place in catalog["places"]:
        if args.city and place["city"] != args.city:
            continue
        if args.district and place.get("district") != args.district:
            continue
        if args.category and place["category"] != args.category:
            continue
        if args.contributor_id and args.contributor_id not in place.get("contributors", []):
            continue
        if required_tags and not required_tags.issubset(set(place.get("tags", []))):
            opinion_tags = {
                tag
                for opinion in opinions_by_place.get(place["place_id"], [])
                for tag in opinion.get("tags", [])
            }
            if not required_tags.issubset(opinion_tags):
                continue

        distance_km = None
        coords = place.get("coordinates")
        if args.near_lat is not None or args.near_lng is not None:
            if args.near_lat is None or args.near_lng is None:
                raise SystemExit("--near-lat and --near-lng must be provided together.")
            if not coords:
                continue
            if args.coord_system and coords.get("coord_system") != args.coord_system:
                continue
            distance_km = haversine_km(args.near_lat, args.near_lng, coords["lat"], coords["lng"])
            if distance_km > args.radius_km:
                continue

        text_score = score_text_match(args.text, place.get("search_text", ""))
        if args.text and text_score == 0:
            continue

        results.append(
            {
                **place,
                "distance_km": distance_km,
                "text_score": text_score,
            }
        )

    if args.near_lat is not None and args.near_lng is not None:
        results.sort(key=lambda item: (item["distance_km"], -item["opinion_count"], item["name"]))
    elif args.text:
        results.sort(key=lambda item: (-item["text_score"], -item["opinion_count"], item["name"]))
    else:
        results.sort(key=lambda item: (-item["opinion_count"], item["name"]))

    results = results[: args.limit]
    if args.json:
        print(json.dumps({"count": len(results), "results": results}, ensure_ascii=False, indent=2))
        return 0

    if not results:
        print("No matching places found.")
        return 1

    for index, item in enumerate(results, start=1):
        headline = f"{index}. {item['name']} | {item['city']}"
        if item.get("district"):
            headline += f" / {item['district']}"
        headline += f" | {item['category']}"
        print(headline)
        if item.get("tags"):
            print(f"   tags: {', '.join(item['tags'])}")
        if item.get("distance_km") is not None:
            print(f"   distance: {item['distance_km']:.2f} km")
        if item.get("latest_summary"):
            print(f"   latest: {item['latest_summary']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

