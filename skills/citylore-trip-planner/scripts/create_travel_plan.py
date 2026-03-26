#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CURATOR_SCRIPTS_DIR = SCRIPT_DIR.parents[1] / "citylore-curator" / "scripts"
if str(CURATOR_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(CURATOR_SCRIPTS_DIR))

from citylore_utils import (
    build_catalog_structure,
    find_repo_root,
    iter_place_records,
    read_json,
    relative_to_repo,
    score_text_match,
    stable_id,
    utc_now_iso,
    write_json,
    write_text,
)

SLOT_DURATION = {
    "morning": 75,
    "lunch": 90,
    "afternoon": 120,
    "dinner": 90,
    "evening": 120,
}

FALLBACK_ORDER = {
    "morning": ["morning", "afternoon", "lunch", "dinner", "evening"],
    "lunch": ["lunch", "dinner", "afternoon", "morning", "evening"],
    "afternoon": ["afternoon", "morning", "lunch", "dinner", "evening"],
    "dinner": ["dinner", "lunch", "evening", "afternoon", "morning"],
    "evening": ["evening", "dinner", "afternoon", "lunch", "morning"],
}


def display_travel_mode(travel_mode: str | None) -> str | None:
    if travel_mode == "companion":
        return "结伴"
    if travel_mode == "solo":
        return "个人"
    return travel_mode


def infer_lodging_kind(name: str | None, district: str | None, explicit_kind: str | None) -> str | None:
    if explicit_kind:
        return explicit_kind
    if name:
        return "hotel"
    if district:
        return "district"
    return None


def load_profile(repo_root: Path, profile_id: str | None) -> dict | None:
    if not profile_id:
        return None
    profile_path = repo_root / "data" / "profiles" / profile_id / "profile.json"
    if not profile_path.exists():
        raise SystemExit(f"Profile not found: {relative_to_repo(repo_root, profile_path)}")
    return read_json(profile_path)


def planning_context(profile: dict | None, requested_mode: str | None) -> dict:
    context = {
        "profile_id": None,
        "travel_mode": requested_mode,
        "planning_style": "balanced",
        "late_start": False,
        "pace": "balanced",
        "prefer_evening": False,
        "plan_notes": [],
    }
    if not profile:
        return context

    preferences = profile.get("travel_preferences") or {}
    travel_mode = requested_mode or preferences.get("default_mode") or "solo"
    mode_preferences = preferences.get(travel_mode) or {}
    start_time = mode_preferences.get("preferred_start_time")
    lodging = mode_preferences.get("lodging_preferences") or {}
    plan_notes = []

    late_start = mode_preferences.get("late_start_likelihood") == "high"
    pace = mode_preferences.get("pace") or "balanced"
    prefer_evening = bool(mode_preferences.get("night_activity_preferences"))

    if late_start:
        if start_time:
            plan_notes.append(f"按画像偏好尽量午后启动，建议 {start_time} 后出门。")
        else:
            plan_notes.append("按画像偏好尽量避免早起行程。")
    if pace == "relaxed":
        plan_notes.append("按画像偏好保持轻松节奏，避免高密度连打卡。")
    if prefer_evening:
        plan_notes.append("按画像偏好保留夜市、夜游或夜间散步时段。")
    if lodging:
        minimum_star_rating = lodging.get("minimum_star_rating")
        preferred_brands = lodging.get("preferred_brands") or []
        fragments = []
        if preferred_brands:
            fragments.append(f"优先品牌 {', '.join(preferred_brands)}")
        if minimum_star_rating is not None:
            fragments.append(f"最低 {minimum_star_rating} 星")
        if fragments:
            plan_notes.append(f"住宿偏好：{'；'.join(fragments)}。")
        if lodging.get("notes"):
            plan_notes.append(lodging["notes"])
    if mode_preferences.get("notes"):
        plan_notes.append(mode_preferences["notes"])

    context.update(
        {
            "profile_id": profile.get("contributor_id"),
            "travel_mode": travel_mode,
            "planning_style": "balanced",
            "late_start": late_start,
            "pace": pace,
            "prefer_evening": prefer_evening,
            "plan_notes": plan_notes,
        }
    )
    return context


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CityLore travel plan from canonical places.")
    parser.add_argument("--repo-root", help="Override CityLore repo root.")
    parser.add_argument("--plan-id", help="Fixed plan file stem for overwrite-friendly updates.")
    parser.add_argument("--city", required=True)
    parser.add_argument("--days", type=int, required=True)
    parser.add_argument("--nights", type=int, default=0)
    parser.add_argument("--title")
    parser.add_argument("--theme", action="append", default=[])
    parser.add_argument("--place-id", action="append", default=[])
    parser.add_argument("--source-ref", action="append", default=[])
    parser.add_argument("--profile-id", help="Contributor profile id, e.g. realRoc.")
    parser.add_argument("--travel-mode", choices=["solo", "companion"], help="Override profile travel mode.")
    parser.add_argument("--planning-style", choices=["classic", "balanced", "local"], default="balanced")
    parser.add_argument("--stay-name", help="Fixed hotel or stay anchor name.")
    parser.add_argument("--stay-district", help="Preferred stay district or business area.")
    parser.add_argument(
        "--stay-kind",
        choices=["hotel", "district", "commercial-area", "neighborhood"],
        help="Explicit stay anchor type.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def infer_slot(category: str, tags: list[str], search_text: str) -> str:
    haystack = " ".join([category, *tags, search_text]).casefold()
    if any(keyword in haystack for keyword in ["cafe", "coffee", "bakery", "brunch", "早餐", "咖啡"]):
        return "morning"
    if any(keyword in haystack for keyword in ["night", "bar", "酒", "夜市", "夜游", "street", "街区"]):
        return "evening"
    if any(keyword in haystack for keyword in ["food", "restaurant", "snack", "小吃", "餐", "饭店"]):
        return "dinner"
    if any(keyword in haystack for keyword in ["museum", "gallery", "market", "park", "walk", "attraction", "陶艺", "瓷器"]):
        return "afternoon"
    return "lunch"


def day_slots(days: int, nights: int, context: dict | None = None) -> list[list[str]]:
    context = context or {}
    late_start = context.get("late_start", False)
    pace = context.get("pace", "balanced")
    prefer_evening = context.get("prefer_evening", False)
    slots = []
    for day_index in range(1, days + 1):
        if late_start:
            if day_index == days:
                current = ["lunch", "afternoon"]
            elif prefer_evening and pace != "compact":
                current = ["lunch", "afternoon", "evening"]
            elif prefer_evening and pace == "compact":
                current = ["lunch", "afternoon", "dinner", "evening"]
            else:
                current = ["lunch", "afternoon", "dinner"]
            slots.append(current)
            continue
        current = ["morning", "afternoon", "dinner"]
        if day_index == days:
            current = ["morning", "lunch", "afternoon"]
        if day_index <= nights:
            current.append("evening")
        slots.append(current)
    return slots


def style_score(item: dict, preferred_slot: str, planning_style: str) -> int:
    tags = set(item.get("tags", []))
    category = item.get("category")
    score = 0
    if planning_style == "local":
        if preferred_slot == "evening":
            score += 2
        if category in {"food", "restaurant", "walk"}:
            score += 2
        if category == "cafe":
            score += 3
        if category == "market":
            score += 2
        if category in {"museum", "attraction"}:
            score -= 2
        if {"local", "snack", "street", "night-walk"} & tags:
            score += 2
        if {"design", "gallery", "specialty-coffee"} & tags:
            score += 1
    if planning_style == "classic":
        if category in {"museum", "attraction"}:
            score += 2
        if category in {"food", "restaurant", "cafe"}:
            score -= 1
    return score


def select_places(
    catalog: dict,
    city: str,
    themes: list[str],
    explicit_ids: list[str],
    context: dict | None = None,
) -> list[dict]:
    context = context or {}
    theme_query = " ".join(themes).strip()
    places = [item for item in catalog["places"] if item["city"] == city]
    if explicit_ids:
        ranked = []
        for place_id in explicit_ids:
            for item in places:
                if item["place_id"] == place_id:
                    ranked.append(item)
                    break
        return ranked

    scored = []
    for item in places:
        preferred_slot = infer_slot(item["category"], item.get("tags", []), item.get("search_text", ""))
        if context.get("late_start") and item.get("category") == "cafe" and preferred_slot == "morning":
            preferred_slot = "afternoon"
        score = item.get("opinion_count", 0) * 2
        if theme_query:
            score += score_text_match(theme_query, item.get("search_text", "")) * 3
        if item.get("latest_summary"):
            score += 1
        if item.get("coordinates"):
            score += 1
        if context.get("prefer_evening") and preferred_slot == "evening":
            score += 2
        if context.get("late_start") and preferred_slot == "morning":
            score -= 1
        if context.get("pace") == "relaxed" and preferred_slot in {"afternoon", "evening"}:
            score += 1
        score += style_score(item, preferred_slot, context.get("planning_style", "balanced"))
        scored.append(
            {
                **item,
                "preferred_slot": preferred_slot,
                "rank_score": score,
            }
        )
    scored.sort(key=lambda item: (-item["rank_score"], -item["opinion_count"], item["name"]))
    return scored


def build_itinerary(
    selected: list[dict],
    days: int,
    nights: int,
    context: dict | None = None,
) -> tuple[list[dict], list[str]]:
    used = set()
    used_categories: dict[str, int] = {}
    plans = []
    selected_place_ids = []
    slot_groups: dict[str, list[dict]] = {}
    for item in selected:
        slot_groups.setdefault(item.get("preferred_slot", "afternoon"), []).append(item)

    fallback = list(selected)
    for day_index, slots in enumerate(day_slots(days, nights, context=context), start=1):
        items = []
        for slot in slots:
            chosen = None
            for candidate_slot in FALLBACK_ORDER[slot]:
                available = [
                    (index, candidate)
                    for index, candidate in enumerate(slot_groups.get(candidate_slot, []))
                    if candidate["place_id"] not in used
                ]
                if available:
                    available.sort(
                        key=lambda item: (
                            used_categories.get(item[1]["category"], 0) * 2 - item[1]["rank_score"],
                            item[0],
                        )
                    )
                    chosen = available[0][1]
                if chosen:
                    break
            if not chosen:
                available = [
                    (index, candidate)
                    for index, candidate in enumerate(fallback)
                    if candidate["place_id"] not in used
                ]
                if available:
                    available.sort(
                        key=lambda item: (
                            used_categories.get(item[1]["category"], 0) * 2 - item[1]["rank_score"],
                            item[0],
                        )
                    )
                    chosen = available[0][1]
            if not chosen:
                continue
            used.add(chosen["place_id"])
            used_categories[chosen["category"]] = used_categories.get(chosen["category"], 0) + 1
            selected_place_ids.append(chosen["place_id"])
            items.append(
                {
                    "slot": slot,
                    "place_id": chosen["place_id"],
                    "name": chosen["name"],
                    "district": chosen.get("district"),
                    "category": chosen["category"],
                    "duration_min": SLOT_DURATION[slot],
                    "reason": chosen.get("latest_summary")
                    or f"{chosen['name']} 是 {chosen['city']} 的推荐地点。",
                }
            )
        if items:
            summary = " -> ".join(item["name"] for item in items)
            plans.append(
                {
                    "day": day_index,
                    "summary": summary,
                    "items": items,
                }
            )
    return plans, selected_place_ids


def infer_lodging_anchor(
    selected: list[dict],
    place_ids: list[str],
    stay_name: str | None,
    stay_district: str | None,
    stay_kind: str | None,
    context: dict,
) -> dict | None:
    if stay_name or stay_district:
        kind = infer_lodging_kind(stay_name, stay_district, stay_kind)
        notes = []
        if stay_district:
            notes.append(f"按用户要求优先住在 {stay_district}")
        if stay_name:
            notes.append(f"按用户要求将住宿锚点定为 {stay_name}")
        if context.get("planning_style") == "local":
            notes.append("该计划会围绕住宿锚点附近的本地吃喝和夜间活动展开。")
        return {
            "kind": kind,
            "name": stay_name,
            "district": stay_district,
            "source": "user",
            "notes": "；".join(notes) if notes else None,
        }

    selected_by_id = {item["place_id"]: item for item in selected}
    district_counts: dict[str, int] = {}
    anchor_names: list[str] = []
    for place_id in place_ids:
        item = selected_by_id.get(place_id)
        if not item:
            continue
        district = item.get("district")
        if district:
            district_counts[district] = district_counts.get(district, 0) + 1
            if len(anchor_names) < 3:
                anchor_names.append(item["name"])

    if not district_counts:
        return None

    district = sorted(district_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    notes = [f"自动推断住宿锚点在 {district}，因为大多数入选地点集中在这里。"]
    if anchor_names:
        notes.append(f"这一带串联 {', '.join(anchor_names)} 会更顺。")
    if context.get("planning_style") == "local":
        notes.append("优先把住宿放在夜间氛围和本地吃喝密度更高的片区。")
    return {
        "kind": "district",
        "name": district,
        "district": district,
        "source": "inferred",
        "notes": " ".join(notes),
    }


def render_markdown(plan: dict) -> str:
    lines = [f"# {plan['title']}", ""]
    lines.extend(
        [
            "## 行程概览",
            "",
            "| 字段 | 内容 |",
            "| --- | --- |",
            f"| 城市 | {plan['city']} |",
            f"| 时长 | {plan['days']} 天 {plan['nights']} 晚 |",
        ]
    )
    if plan.get("profile_id"):
        lines.append(f"| Profile | {plan['profile_id']} |")
    if plan.get("travel_mode"):
        lines.append(f"| 出行模式 | {display_travel_mode(plan['travel_mode'])} |")
    if plan.get("planning_style"):
        lines.append(f"| 玩法风格 | {plan['planning_style']} |")
    if plan.get("lodging_anchor"):
        lodging_anchor = plan["lodging_anchor"]
        summary = lodging_anchor.get("name") or lodging_anchor.get("district")
        if summary:
            lines.append(f"| 住宿锚点 | {summary} |")
    if plan.get("themes"):
        lines.append(f"| 主题 | {', '.join(plan['themes'])} |")
    lines.append("")
    if plan.get("plan_notes"):
        lines.append("## 规划备注")
        lines.append("")
        for note in plan["plan_notes"]:
            lines.append(f"- {note}")
        lines.append("")
    for day in plan["itinerary"]:
        lines.append(f"## Day {day['day']}")
        lines.append("")
        lines.append(f"> {day['summary']}")
        lines.append("")
        lines.append("| 时间段 | 地点 | 区域 | 类型 | 建议停留 | 推荐理由 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for item in day["items"]:
            district = item.get("district") or "-"
            duration = f"{item['duration_min']} 分钟" if item.get("duration_min") else "-"
            reason = item["reason"].replace("\n", " ").replace("|", "\\|")
            lines.append(
                f"| {item['slot']} | {item['name']} | {district} | {item['category']} | {duration} | {reason} |"
            )
        lines.append("")
    if plan.get("lodging_recommendations"):
        lines.append("## 住宿推荐")
        lines.append("")
        lines.append("| 名称 | 区域 | 定位 | 适合什么情况 | 备注 | 预订链接 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for item in plan["lodging_recommendations"]:
            district = item.get("district") or "-"
            tier = item.get("tier") or "-"
            reason = item["reason"].replace("\n", " ").replace("|", "\\|")
            notes = (item.get("notes") or "-").replace("\n", " ").replace("|", "\\|")
            booking_ref = item.get("booking_ref")
            link = f"[查看]({booking_ref})" if booking_ref else "-"
            lines.append(f"| {item['name']} | {district} | {tier} | {reason} | {notes} | {link} |")
        lines.append("")
    if plan.get("food_recommendations"):
        lines.append("## 美食推荐")
        lines.append("")
        lines.append("| 名称 | 区域 | 类型 | 推荐点单/关键词 | 适合什么情况 | 备注 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for item in plan["food_recommendations"]:
            district = item.get("district") or "-"
            category = item.get("category") or "-"
            signature = (item.get("signature") or "-").replace("\n", " ").replace("|", "\\|")
            reason = item["reason"].replace("\n", " ").replace("|", "\\|")
            notes = (item.get("notes") or "-").replace("\n", " ").replace("|", "\\|")
            lines.append(f"| {item['name']} | {district} | {category} | {signature} | {reason} | {notes} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path(__file__))
    if args.nights > args.days:
        raise SystemExit("--nights cannot exceed --days.")
    if args.plan_id and ("/" in args.plan_id or args.plan_id in {".", ".."}):
        raise SystemExit("--plan-id cannot contain path separators.")

    catalog = build_catalog_structure(repo_root)
    profile = load_profile(repo_root, args.profile_id)
    context = planning_context(profile, args.travel_mode)
    context["planning_style"] = args.planning_style
    if args.planning_style == "local":
        context["plan_notes"].append("本次行程按本地精华玩法编排，优先真实好玩和可重复去的地方，不只堆游客点。")
    selected = select_places(
        catalog,
        city=args.city,
        themes=args.theme,
        explicit_ids=args.place_id,
        context=context,
    )
    if not selected:
        raise SystemExit(f"No canonical places found for city={args.city}.")

    itinerary, place_ids = build_itinerary(
        selected=selected,
        days=args.days,
        nights=args.nights,
        context=context,
    )
    if not itinerary:
        raise SystemExit("Could not build an itinerary from the available places.")
    lodging_anchor = infer_lodging_anchor(
        selected=selected,
        place_ids=place_ids,
        stay_name=args.stay_name,
        stay_district=args.stay_district,
        stay_kind=args.stay_kind,
        context=context,
    )
    if lodging_anchor and lodging_anchor.get("notes"):
        context["plan_notes"].append(lodging_anchor["notes"])

    now_iso = utc_now_iso()
    title = args.title or args.plan_id or f"{args.city}{args.days}天{args.nights}晚旅行计划"
    plan_id = args.plan_id or stable_id(
        "plan",
        title,
        args.city,
        str(args.days),
        str(args.nights),
        ",".join(args.theme),
    )
    json_path = repo_root / "data" / "plans" / f"{plan_id}.json"
    md_path = repo_root / "data" / "plans" / f"{plan_id}.md"

    place_records = {record["place_id"]: record for record in iter_place_records(repo_root)}
    derived_source_refs = []
    for place_id in place_ids:
        derived_source_refs.extend(place_records.get(place_id, {}).get("source_refs", []))

    plan = {
        "plan_id": plan_id,
        "title": title,
        "city": args.city,
        "days": args.days,
        "profile_id": context.get("profile_id"),
        "travel_mode": context.get("travel_mode"),
        "planning_style": context.get("planning_style"),
        "nights": args.nights,
        "themes": args.theme,
        "source_refs": sorted(set([*args.source_ref, *derived_source_refs])),
        "place_ids": place_ids,
        "plan_notes": context.get("plan_notes", []),
        "lodging_anchor": lodging_anchor,
        "itinerary": itinerary,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    write_json(json_path, plan)
    write_text(md_path, render_markdown(plan))

    result = {
        "plan_id": plan_id,
        "json_path": relative_to_repo(repo_root, json_path),
        "markdown_path": relative_to_repo(repo_root, md_path),
        "place_count": len(place_ids),
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Plan: {plan_id}")
        print(f"JSON: {result['json_path']}")
        print(f"Markdown: {result['markdown_path']}")
        print(f"Places used: {result['place_count']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
