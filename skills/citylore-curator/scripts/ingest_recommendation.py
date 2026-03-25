#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from citylore_utils import (
    build_exports,
    find_repo_root,
    iter_area_records,
    iter_place_records,
    merge_unique,
    normalize_match,
    relative_to_repo,
    stable_hash,
    stable_id,
    unique_sorted,
    utc_now_iso,
    write_json,
    write_text,
)
from resolve_coordinates import resolve_candidates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest a recommendation into CityLore.")
    parser.add_argument("--repo-root", help="Override CityLore repo root.")
    parser.add_argument("--contributor-id", required=True)
    parser.add_argument("--place-name", required=True)
    parser.add_argument("--city", required=True)
    parser.add_argument("--country", default="CN")
    parser.add_argument("--district")
    parser.add_argument("--address")
    parser.add_argument("--category", default="local-place")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--good-for", action="append", default=[])
    parser.add_argument("--avoid-if", action="append", default=[])
    parser.add_argument("--title")
    parser.add_argument("--summary")
    parser.add_argument("--body", required=True)
    parser.add_argument("--text", help="Original note text.")
    parser.add_argument("--text-file", help="Path to original note text.")
    parser.add_argument("--audio-file", help="Path to original audio note.")
    parser.add_argument(
        "--source-kind",
        default="text",
        choices=["text", "audio", "transcript"],
        help="Origin of the note stored in imports/manual/raw.",
    )
    parser.add_argument("--visit-date", help="YYYY-MM-DD")
    parser.add_argument("--rating", type=float)
    parser.add_argument("--price-level", type=int, choices=[0, 1, 2, 3, 4])
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lng", type=float)
    parser.add_argument("--coord-system", choices=["wgs84", "gcj02", "bd09"])
    parser.add_argument("--coord-provider", help="Provider label when lat/lng is supplied manually.")
    parser.add_argument("--provider-place-id", help="External provider place identifier.")
    parser.add_argument("--resolve-coordinates", action="store_true")
    parser.add_argument("--poi-provider", default="none", choices=["none", "amap", "nominatim"])
    parser.add_argument("--location-query", help="Override query string for coordinate lookup.")
    parser.add_argument("--countrycode", help="Country code hint for nominatim, e.g. cn.")
    parser.add_argument("--whisper-model", default="turbo")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def load_text_from_args(args: argparse.Namespace) -> str:
    if args.text:
        return args.text.strip()
    if args.text_file:
        return Path(args.text_file).read_text(encoding="utf-8").strip()
    if args.audio_file:
        return transcribe_audio(Path(args.audio_file), args.whisper_model).strip()
    return args.body.strip()


def transcribe_audio(audio_path: Path, model: str) -> str:
    whisper_bin = shutil.which("whisper")
    if not whisper_bin:
        raise RuntimeError("Audio ingest requires the local whisper CLI or an explicit --text/--text-file.")

    with tempfile.TemporaryDirectory(prefix="citylore-whisper-") as temp_dir:
        subprocess.run(
            [
                whisper_bin,
                str(audio_path),
                "--model",
                model,
                "--output_format",
                "txt",
                "--output_dir",
                temp_dir,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        txt_files = sorted(Path(temp_dir).glob("*.txt"))
        if not txt_files:
            raise RuntimeError("Whisper did not produce a transcript file.")
        return txt_files[0].read_text(encoding="utf-8")


def resolve_best_coordinates(args: argparse.Namespace) -> dict | None:
    if args.lat is not None or args.lng is not None:
        if args.lat is None or args.lng is None:
            raise RuntimeError("--lat and --lng must be supplied together.")
        if not args.coord_system:
            raise RuntimeError("--coord-system is required when supplying manual coordinates.")
        return {
            "lat": args.lat,
            "lng": args.lng,
            "coord_system": args.coord_system,
            "provider": args.coord_provider or "manual",
            "provider_place_id": args.provider_place_id,
            "confidence": None,
        }

    if not args.resolve_coordinates or args.poi_provider == "none":
        return None

    query = args.location_query or " ".join(
        part for part in [args.city, args.district, args.place_name, args.address] if part
    ).strip()
    candidates = resolve_candidates(
        query=query,
        city=args.city,
        provider=args.poi_provider,
        limit=3,
        countrycode=args.countrycode,
    )
    if not candidates:
        return None
    best = candidates[0]
    return {
        "lat": best["lat"],
        "lng": best["lng"],
        "coord_system": best["coord_system"],
        "provider": best["provider"],
        "provider_place_id": best.get("provider_place_id"),
        "confidence": best.get("confidence"),
        "provider_formatted": best.get("formatted_address"),
    }


def find_matching_area(repo_root: Path, city: str, district: str | None) -> dict | None:
    if not district:
        return None
    district_key = normalize_match(district)
    city_key = normalize_match(city)
    for area in iter_area_records(repo_root):
        if normalize_match(area.get("name")) == district_key and normalize_match(area.get("city")) == city_key:
            return area
    return None


def ensure_area_record(repo_root: Path, city: str, country: str, district: str | None, now_iso: str) -> tuple[str | None, Path | None]:
    if not district:
        return None, None
    existing = find_matching_area(repo_root, city=city, district=district)
    if existing:
        return existing["area_id"], repo_root / "data" / "areas" / f"{existing['area_id']}.json"

    area_id = stable_id("area", district, city, country)
    path = repo_root / "data" / "areas" / f"{area_id}.json"
    payload = {
        "area_id": area_id,
        "name": district,
        "aliases": [],
        "type": "district",
        "country": country,
        "city": city,
        "parent_area_id": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    write_json(path, payload)
    return area_id, path


def match_existing_place(repo_root: Path, args: argparse.Namespace) -> tuple[dict | None, Path | None]:
    provider_key = normalize_match(args.provider_place_id)
    name_key = normalize_match(args.place_name)
    city_key = normalize_match(args.city)
    district_key = normalize_match(args.district)

    for path in sorted((repo_root / "data" / "places").glob("*/place.json")):
        place = json.loads(path.read_text(encoding="utf-8"))
        coords = place.get("coordinates") or {}
        if provider_key and normalize_match(coords.get("provider_place_id")) == provider_key:
            return place, path
        if normalize_match(place.get("name")) != name_key:
            continue
        if normalize_match(place.get("city")) != city_key:
            continue
        if district_key and normalize_match(place.get("district")) != district_key:
            continue
        return place, path
    return None, None


def build_source_markdown(
    source_id: str,
    args: argparse.Namespace,
    source_text: str,
    resolved_coordinates: dict | None,
    now_iso: str,
) -> str:
    lines = [
        "# Manual Recommendation Source",
        "",
        f"- source_id: {source_id}",
        f"- captured_at: {now_iso}",
        f"- contributor_id: {args.contributor_id}",
        f"- source_kind: {args.source_kind}",
        f"- place_name: {args.place_name}",
        f"- city: {args.city}",
    ]
    if args.district:
        lines.append(f"- district: {args.district}")
    if args.address:
        lines.append(f"- address: {args.address}")
    if args.audio_file:
        lines.append(f"- audio_file: {args.audio_file}")
    if resolved_coordinates:
        lines.append(f"- coord_provider: {resolved_coordinates.get('provider')}")
        lines.append(f"- coord_system: {resolved_coordinates.get('coord_system')}")
        lines.append(f"- coordinates: {resolved_coordinates.get('lat')},{resolved_coordinates.get('lng')}")

    lines.extend(["", "## Raw Content", "", source_text.strip(), ""])
    return "\n".join(lines)


def summarize_body(body: str, max_length: int = 90) -> str:
    compact = " ".join(body.split())
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 1].rstrip() + "…"


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path(__file__))
    now_iso = utc_now_iso()
    source_text = load_text_from_args(args)
    resolved_coordinates = resolve_best_coordinates(args)

    source_id = stable_id(
        "src",
        args.place_name,
        args.contributor_id,
        now_iso,
        stable_hash(args.body, length=6),
    )
    raw_path = repo_root / "imports" / "manual" / "raw" / f"{source_id}.md"
    raw_relative = relative_to_repo(repo_root, raw_path)

    existing_place, existing_place_path = match_existing_place(repo_root, args)
    area_id = None
    area_path = None
    if args.district:
        existing_area = find_matching_area(repo_root, city=args.city, district=args.district)
        if existing_area:
            area_id = existing_area["area_id"]
            area_path = repo_root / "data" / "areas" / f"{area_id}.json"

    if not existing_place:
        place_id = stable_id("place", args.place_name, args.city, args.district or "", args.country)
        place_path = repo_root / "data" / "places" / place_id / "place.json"
    else:
        place_id = existing_place["place_id"]
        place_path = existing_place_path

    opinion_id = stable_id(
        "opn",
        args.place_name,
        args.contributor_id,
        now_iso,
        stable_hash(args.body, length=6),
    )
    opinion_path = repo_root / "data" / "opinions" / args.contributor_id / f"{opinion_id}.json"

    if not args.dry_run and args.district and not area_id:
        area_id, area_path = ensure_area_record(
            repo_root=repo_root,
            city=args.city,
            country=args.country,
            district=args.district,
            now_iso=now_iso,
        )

    provider_formatted = None
    coordinates = None
    if resolved_coordinates:
        provider_formatted = resolved_coordinates.pop("provider_formatted", None)
        coordinates = resolved_coordinates

    source_markdown = build_source_markdown(
        source_id=source_id,
        args=args,
        source_text=source_text,
        resolved_coordinates=coordinates,
        now_iso=now_iso,
    )

    tag_values = unique_sorted(args.tag)
    if existing_place:
        place_payload = {
            **existing_place,
            "name": existing_place.get("name") or args.place_name,
            "country": existing_place.get("country") or args.country,
            "city": existing_place.get("city") or args.city,
            "district": existing_place.get("district") or args.district,
            "area_refs": merge_unique(existing_place.get("area_refs", []), [area_id] if area_id else []),
            "category": existing_place.get("category") or args.category,
            "tags": merge_unique(existing_place.get("tags", []), tag_values),
            "address": {
                "full_text": existing_place.get("address", {}).get("full_text") or args.address,
                "provider_formatted": existing_place.get("address", {}).get("provider_formatted")
                or provider_formatted,
            },
            "coordinates": existing_place.get("coordinates") or coordinates,
            "price_level": existing_place.get("price_level")
            if existing_place.get("price_level") is not None
            else args.price_level,
            "source_refs": merge_unique(existing_place.get("source_refs", []), [raw_relative]),
            "notes": existing_place.get("notes"),
            "created_at": existing_place.get("created_at") or now_iso,
            "updated_at": now_iso,
        }
    else:
        place_payload = {
            "place_id": place_id,
            "name": args.place_name,
            "aliases": [],
            "country": args.country,
            "city": args.city,
            "district": args.district,
            "area_refs": [area_id] if area_id else [],
            "category": args.category,
            "tags": tag_values,
            "address": {
                "full_text": args.address,
                "provider_formatted": provider_formatted,
            },
            "coordinates": coordinates,
            "price_level": args.price_level,
            "source_refs": [raw_relative],
            "notes": None,
            "created_at": now_iso,
            "updated_at": now_iso,
        }

    opinion_payload = {
        "opinion_id": opinion_id,
        "place_id": place_id,
        "contributor_id": args.contributor_id,
        "title": args.title,
        "summary": args.summary or summarize_body(args.body),
        "body": args.body,
        "rating": args.rating,
        "source_kind": args.source_kind,
        "source_ref": raw_relative,
        "visit_date": args.visit_date,
        "tags": tag_values,
        "signals": {
            "good_for": unique_sorted(args.good_for),
            "avoid_if": unique_sorted(args.avoid_if),
        },
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    if not args.dry_run:
        write_text(raw_path, source_markdown)
        write_json(place_path, place_payload)
        write_json(opinion_path, opinion_payload)
        export_result = build_exports(repo_root)
    else:
        export_result = {
            "catalog_path": ".citylore/exports/catalog.json",
            "places_path": ".citylore/exports/places.ndjson",
            "opinions_path": ".citylore/exports/opinions.ndjson",
        }

    result = {
        "repo_root": str(repo_root),
        "dry_run": args.dry_run,
        "created_or_updated": {
            "raw_source": raw_relative,
            "place": relative_to_repo(repo_root, place_path),
            "opinion": relative_to_repo(repo_root, opinion_path),
            "area": relative_to_repo(repo_root, area_path) if area_path else None,
        },
        "place_id": place_id,
        "opinion_id": opinion_id,
        "exports": export_result,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Raw source: {result['created_or_updated']['raw_source']}")
        if result["created_or_updated"]["area"]:
            print(f"Area: {result['created_or_updated']['area']}")
        print(f"Place: {result['created_or_updated']['place']}")
        print(f"Opinion: {result['created_or_updated']['opinion']}")
        print(f"Catalog: {export_result['catalog_path']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

