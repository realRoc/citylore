#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CURATOR_SCRIPTS_DIR = SCRIPT_DIR.parents[1] / "citylore-curator" / "scripts"
if str(CURATOR_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(CURATOR_SCRIPTS_DIR))

from citylore_utils import (
    find_repo_root,
    merge_unique,
    normalize_match,
    relative_to_repo,
    stable_id,
    unique_sorted,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Store and promote a Xiaohongshu city research batch.")
    parser.add_argument("--repo-root", help="Override CityLore repo root.")
    parser.add_argument("--normalized-file", required=True, help="JSON file with normalized candidates.")
    parser.add_argument("--raw-file", help="Optional raw JSON file from xiaohongshu-mcp output.")
    parser.add_argument("--city", help="Override city.")
    parser.add_argument("--country", default="CN")
    parser.add_argument("--batch-name", help="Human-friendly batch name.")
    parser.add_argument("--curator-id", default="xhs-city-research")
    parser.add_argument("--poi-provider", default="none", choices=["none", "amap", "nominatim"])
    parser.add_argument("--promote-limit", type=int, default=12)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {"candidates": payload}
    return payload


def infer_city(payload: dict, override: str | None) -> str:
    if override:
        return override
    if payload.get("city"):
        return str(payload["city"])
    for candidate in payload.get("candidates", []):
        if candidate.get("city"):
            return str(candidate["city"])
    raise RuntimeError("Could not infer city from normalized batch. Use --city.")


def merge_candidates(payload: dict, city: str) -> list[dict]:
    merged: dict[str, dict] = {}
    for item in payload.get("candidates", []):
        place_name = (item.get("place_name") or "").strip()
        if not place_name:
            continue
        district = (item.get("district") or "").strip() or None
        address = (item.get("address") or "").strip() or None
        category = (item.get("category") or "local-place").strip()
        candidate_city = (item.get("city") or city).strip()
        key = "||".join(
            [normalize_match(candidate_city), normalize_match(district), normalize_match(place_name)]
        )
        existing = merged.get(key)
        source_refs = [
            {
                "source_feed_id": item.get("source_feed_id"),
                "source_title": item.get("source_title"),
                "source_author": item.get("source_author"),
            }
        ]
        if not existing:
            merged[key] = {
                "candidate_id": stable_id("xhs", place_name, candidate_city, district or ""),
                "place_name": place_name,
                "city": candidate_city,
                "district": district,
                "address": address,
                "category": category,
                "tags": unique_sorted(str(tag) for tag in item.get("tags", [])),
                "why_go": (item.get("why_go") or "").strip() or None,
                "body": (item.get("body") or item.get("why_go") or "").strip() or None,
                "priority": float(item.get("priority", 0.5)),
                "source_refs": source_refs,
                "location_query": item.get("location_query"),
            }
            continue

        existing["tags"] = merge_unique(existing.get("tags", []), item.get("tags", []))
        existing["priority"] = max(float(existing.get("priority", 0.5)), float(item.get("priority", 0.5)))
        if not existing.get("address") and address:
            existing["address"] = address
        if not existing.get("why_go") and item.get("why_go"):
            existing["why_go"] = item["why_go"].strip()
        if not existing.get("body") and item.get("body"):
            existing["body"] = item["body"].strip()
        existing["source_refs"].extend(source_refs)

    candidates = list(merged.values())
    for item in candidates:
        item["source_refs"] = [ref for ref in item["source_refs"] if ref.get("source_feed_id")]
    candidates.sort(key=lambda candidate: (-candidate.get("priority", 0.0), candidate["place_name"]))
    return candidates


def promote_candidates(
    repo_root: Path,
    curator_id: str,
    poi_provider: str,
    candidates: list[dict],
    promote_limit: int,
    dry_run: bool,
) -> list[dict]:
    results = []
    ingest_script = repo_root / "skills" / "citylore-curator" / "scripts" / "ingest_recommendation.py"
    for candidate in candidates[:promote_limit]:
        body = candidate.get("body") or candidate.get("why_go") or f"{candidate['place_name']} 是热门城市推荐地点。"
        source_titles = []
        for ref in candidate.get("source_refs", [])[:3]:
            title_bits = [value for value in [ref.get("source_title"), ref.get("source_author")] if value]
            if title_bits:
                source_titles.append(" / ".join(title_bits))
        text_bits = [
            candidate.get("why_go") or "",
            "；".join(source_titles),
        ]
        text_payload = " ".join(bit for bit in text_bits if bit).strip() or body

        cmd = [
            "python3",
            str(ingest_script),
            "--repo-root",
            str(repo_root),
            "--contributor-id",
            curator_id,
            "--place-name",
            candidate["place_name"],
            "--city",
            candidate["city"],
            "--category",
            candidate.get("category") or "local-place",
            "--body",
            body,
            "--text",
            text_payload,
            "--source-kind",
            "text",
            "--poi-provider",
            poi_provider,
            "--json",
        ]
        if candidate.get("district"):
            cmd.extend(["--district", candidate["district"]])
        if candidate.get("address"):
            cmd.extend(["--address", candidate["address"]])
        if candidate.get("location_query"):
            cmd.extend(["--location-query", candidate["location_query"]])
        elif candidate.get("address"):
            cmd.extend(["--location-query", f"{candidate['city']} {candidate['address']}"])
        if poi_provider != "none":
            cmd.append("--resolve-coordinates")
        for tag in candidate.get("tags", []):
            cmd.extend(["--tag", tag])

        if dry_run:
            results.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "place_name": candidate["place_name"],
                    "status": "dry-run",
                    "command": cmd,
                }
            )
            continue

        completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
        payload = json.loads(completed.stdout)
        results.append(
            {
                "candidate_id": candidate["candidate_id"],
                "place_name": candidate["place_name"],
                "status": "promoted",
                "place_id": payload["place_id"],
                "opinion_id": payload["opinion_id"],
                "paths": payload["created_or_updated"],
            }
        )
    return results


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path(__file__))
    normalized_path = Path(args.normalized_file).resolve()
    payload = load_json(normalized_path)
    city = infer_city(payload, args.city)
    batch_name = args.batch_name or payload.get("batch_name") or normalized_path.stem
    batch_id = stable_id("xhs-batch", batch_name, city)

    raw_payload = load_json(Path(args.raw_file).resolve()) if args.raw_file else payload
    candidates = merge_candidates(payload, city=city)

    raw_path = repo_root / "imports" / "xiaohongshu" / "raw" / f"{batch_id}.json"
    normalized_out_path = repo_root / "imports" / "xiaohongshu" / "normalized" / f"{batch_id}.json"
    candidates_path = repo_root / "imports" / "xiaohongshu" / "candidates" / f"{batch_id}.json"
    mappings_path = repo_root / "imports" / "xiaohongshu" / "mappings" / f"{batch_id}.json"

    normalized_output = {
        **payload,
        "batch_id": batch_id,
        "city": city,
        "candidate_count": len(candidates),
    }
    candidate_output = {
        "batch_id": batch_id,
        "city": city,
        "batch_name": batch_name,
        "candidates": candidates,
    }

    if not args.dry_run:
        write_json(raw_path, raw_payload)
        write_json(normalized_out_path, normalized_output)
        write_json(candidates_path, candidate_output)

    promotions = promote_candidates(
        repo_root=repo_root,
        curator_id=args.curator_id,
        poi_provider=args.poi_provider,
        candidates=candidates,
        promote_limit=args.promote_limit,
        dry_run=args.dry_run,
    )

    mappings_output = {
        "batch_id": batch_id,
        "city": city,
        "mappings": promotions,
    }
    if not args.dry_run:
        write_json(mappings_path, mappings_output)

    result = {
        "batch_id": batch_id,
        "city": city,
        "paths": {
            "raw": relative_to_repo(repo_root, raw_path),
            "normalized": relative_to_repo(repo_root, normalized_out_path),
            "candidates": relative_to_repo(repo_root, candidates_path),
            "mappings": relative_to_repo(repo_root, mappings_path),
        },
        "candidate_count": len(candidates),
        "promotions": promotions,
        "dry_run": args.dry_run,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Batch: {batch_id} | City: {city}")
        print(f"Candidates: {len(candidates)}")
        print(f"Raw: {result['paths']['raw']}")
        print(f"Normalized: {result['paths']['normalized']}")
        print(f"Candidates file: {result['paths']['candidates']}")
        print(f"Mappings: {result['paths']['mappings']}")
        print(f"Promoted: {sum(1 for item in promotions if item.get('status') == 'promoted')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
