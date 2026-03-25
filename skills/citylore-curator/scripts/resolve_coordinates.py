#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def http_get(url: str, params: dict[str, str], headers: dict[str, str] | None = None) -> dict | list:
    query_string = urllib.parse.urlencode({key: value for key, value in params.items() if value})
    request = urllib.request.Request(
        f"{url}?{query_string}",
        headers=headers or {},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def resolve_amap(query: str, city: str | None, limit: int) -> list[dict]:
    api_key = os.environ.get("AMAP_API_KEY")
    if not api_key:
        raise RuntimeError("AMAP_API_KEY is required for provider=amap.")

    payload = http_get(
        "https://restapi.amap.com/v3/place/text",
        {
            "key": api_key,
            "keywords": query,
            "city": city or "",
            "offset": str(limit),
            "page": "1",
            "extensions": "base",
            "output": "json",
        },
    )

    if payload.get("status") != "1":
        raise RuntimeError(payload.get("info") or "AMap request failed.")

    candidates = []
    for item in payload.get("pois", [])[:limit]:
        location = item.get("location") or ""
        if "," not in location:
            continue
        lng_text, lat_text = location.split(",", 1)
        candidates.append(
            {
                "provider": "amap",
                "provider_place_id": item.get("id"),
                "name": item.get("name"),
                "formatted_address": " ".join(
                    part
                    for part in [
                        item.get("pname"),
                        item.get("cityname"),
                        item.get("adname"),
                        item.get("address"),
                    ]
                    if part
                ).strip(),
                "lat": float(lat_text),
                "lng": float(lng_text),
                "coord_system": "gcj02",
                "confidence": None,
                "raw": item,
            }
        )
    return candidates


def resolve_nominatim(query: str, city: str | None, limit: int, countrycode: str | None) -> list[dict]:
    q = " ".join(part for part in [city, query] if part).strip()
    payload = http_get(
        "https://nominatim.openstreetmap.org/search",
        {
            "q": q,
            "format": "jsonv2",
            "limit": str(limit),
            "countrycodes": countrycode or "",
        },
        headers={
            "User-Agent": "citylore-curator/0.1 (+https://github.com/realRoc/citylore)",
        },
    )

    candidates = []
    for item in payload[:limit]:
        candidates.append(
            {
                "provider": "nominatim",
                "provider_place_id": str(item.get("place_id")),
                "name": item.get("name") or item.get("display_name"),
                "formatted_address": item.get("display_name"),
                "lat": float(item["lat"]),
                "lng": float(item["lon"]),
                "coord_system": "wgs84",
                "confidence": None,
                "raw": item,
            }
        )
    return candidates


def resolve_candidates(
    query: str,
    city: str | None = None,
    provider: str = "nominatim",
    limit: int = 5,
    countrycode: str | None = None,
) -> list[dict]:
    if provider == "amap":
        return resolve_amap(query=query, city=city, limit=limit)
    if provider == "nominatim":
        return resolve_nominatim(query=query, city=city, limit=limit, countrycode=countrycode)
    if provider == "none":
        return []
    raise ValueError(f"Unsupported provider: {provider}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve coordinates for a CityLore place candidate.")
    parser.add_argument("--query", required=True, help="POI name or address fragment.")
    parser.add_argument("--city", help="Optional city bias.")
    parser.add_argument(
        "--provider",
        default=os.environ.get("CITYLORE_POI_PROVIDER", "nominatim"),
        choices=["amap", "nominatim", "none"],
        help="Coordinate provider to use.",
    )
    parser.add_argument("--countrycode", help="Optional country code bias, e.g. cn.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidates = resolve_candidates(
        query=args.query,
        city=args.city,
        provider=args.provider,
        limit=args.limit,
        countrycode=args.countrycode,
    )

    if args.json:
        print(json.dumps(candidates, ensure_ascii=False, indent=2))
        return 0

    if not candidates:
        print("No coordinate candidates found.")
        return 1

    for index, item in enumerate(candidates, start=1):
        print(
            f"{index}. {item['name']} | {item['lat']:.6f}, {item['lng']:.6f} "
            f"| {item['coord_system']} | {item['provider']}"
        )
        if item.get("formatted_address"):
            print(f"   {item['formatted_address']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

