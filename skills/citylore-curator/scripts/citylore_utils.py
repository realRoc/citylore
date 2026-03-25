#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Iterable


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def find_repo_root(start: Path | None = None) -> Path:
    origin = (start or Path.cwd()).resolve()
    for candidate in [origin, *origin.parents]:
        if (candidate / ".citylore" / "manifest.yaml").exists():
            return candidate
    raise FileNotFoundError("Could not find CityLore repo root from current path.")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_ndjson(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def relative_to_repo(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def iter_area_records(repo_root: Path) -> list[dict]:
    return [read_json(path) for path in sorted((repo_root / "data" / "areas").glob("*.json"))]


def iter_place_records(repo_root: Path) -> list[dict]:
    return [read_json(path) for path in sorted((repo_root / "data" / "places").glob("*/place.json"))]


def iter_opinion_records(repo_root: Path) -> list[dict]:
    return [read_json(path) for path in sorted((repo_root / "data" / "opinions").glob("*/*.json"))]


def normalize_match(value: str | None) -> str:
    return re.sub(r"[\W_]+", "", (value or "").casefold())


def ascii_slug(value: str | None) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").casefold()).strip("-")
    return cleaned[:48] or "x"


def stable_hash(*parts: str, length: int = 8) -> str:
    joined = "||".join(part.strip() for part in parts if part is not None)
    return sha1(joined.encode("utf-8")).hexdigest()[:length]


def stable_id(prefix: str, label: str, *parts: str, length: int = 8) -> str:
    digest = stable_hash(label, *parts, length=length)
    slug = ascii_slug(label)
    if slug == "x":
        return f"{prefix}-{digest}"
    return f"{prefix}-{slug}-{digest}"


def unique_sorted(values: Iterable[str]) -> list[str]:
    cleaned = []
    seen = set()
    for value in values:
        item = (value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        cleaned.append(item)
    return sorted(cleaned)


def merge_unique(existing: Iterable[str], new_values: Iterable[str]) -> list[str]:
    return unique_sorted([*list(existing), *list(new_values)])


def score_text_match(query: str | None, haystack: str) -> int:
    if not query:
        return 0
    query = query.strip()
    if not query:
        return 0
    tokens = query.split() if " " in query else [query]
    lowered = haystack.casefold()
    score = 0
    for token in tokens:
        probe = token.casefold()
        if probe and probe in lowered:
            score += 1
    return score


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_catalog_structure(repo_root: Path) -> dict:
    places = iter_place_records(repo_root)
    opinions = iter_opinion_records(repo_root)
    opinions_by_place: dict[str, list[dict]] = {}
    for opinion in opinions:
        opinions_by_place.setdefault(opinion["place_id"], []).append(opinion)

    for opinion_list in opinions_by_place.values():
        opinion_list.sort(
            key=lambda item: (item.get("created_at") or "", item.get("opinion_id") or ""),
            reverse=True,
        )

    catalog_places = []
    for place in sorted(places, key=lambda item: item["place_id"]):
        related_opinions = opinions_by_place.get(place["place_id"], [])
        contributors = unique_sorted(item["contributor_id"] for item in related_opinions)
        latest_opinion = related_opinions[0] if related_opinions else None
        search_chunks = [
            place.get("name", ""),
            place.get("city", ""),
            place.get("district", "") or "",
            place.get("category", ""),
            " ".join(place.get("tags", [])),
            place.get("address", {}).get("full_text", "") or "",
            latest_opinion.get("summary", "") if latest_opinion else "",
            " ".join(item.get("body", "") for item in related_opinions[:3]),
        ]
        catalog_places.append(
            {
                "place_id": place["place_id"],
                "name": place["name"],
                "city": place["city"],
                "district": place.get("district"),
                "category": place["category"],
                "tags": place.get("tags", []),
                "coordinates": place.get("coordinates"),
                "opinion_count": len(related_opinions),
                "contributors": contributors,
                "latest_summary": latest_opinion.get("summary") if latest_opinion else None,
                "latest_rating": latest_opinion.get("rating") if latest_opinion else None,
                "search_text": " ".join(chunk for chunk in search_chunks if chunk).strip(),
            }
        )

    return {
        "generated_at": utc_now_iso(),
        "stats": {
            "place_count": len(places),
            "opinion_count": len(opinions),
        },
        "places": catalog_places,
        "opinions": sorted(
            opinions,
            key=lambda item: (item.get("created_at") or "", item.get("opinion_id") or ""),
            reverse=True,
        ),
    }


def build_exports(repo_root: Path) -> dict:
    export_dir = repo_root / ".citylore" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    places = sorted(iter_place_records(repo_root), key=lambda item: item["place_id"])
    opinions = sorted(
        iter_opinion_records(repo_root),
        key=lambda item: (item.get("created_at") or "", item.get("opinion_id") or ""),
        reverse=True,
    )
    catalog = build_catalog_structure(repo_root)

    write_ndjson(export_dir / "places.ndjson", places)
    write_ndjson(export_dir / "opinions.ndjson", opinions)
    write_json(export_dir / "catalog.json", catalog)

    return {
        "catalog_path": relative_to_repo(repo_root, export_dir / "catalog.json"),
        "places_path": relative_to_repo(repo_root, export_dir / "places.ndjson"),
        "opinions_path": relative_to_repo(repo_root, export_dir / "opinions.ndjson"),
        "place_count": len(places),
        "opinion_count": len(opinions),
    }
