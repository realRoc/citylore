---
name: citylore-trip-planner
description: Research a city with local xiaohongshu-mcp search tools, normalize recommended places into CityLore imports and canonical records, and generate a multi-day trip plan. Use when the user asks for a city itinerary such as "景德镇 2 天 1 晚怎么安排" and wants the research added to the repository.
metadata:
  openclaw:
    emoji: "🧭"
    requires:
      bins: ["python3"]
---

# CityLore Trip Planner

## Overview

Use this skill when the user wants a city-level eat-drink-play itinerary sourced from Xiaohongshu research and persisted into CityLore. It orchestrates `xiaohongshu-mcp` search tools, stores the import batch under `imports/xiaohongshu/`, promotes curated places into `data/places/`, and writes a reusable trip plan under `data/plans/`.

Read [references/xiaohongshu-research.md](references/xiaohongshu-research.md) for the search and extraction pattern. Read [references/plan-rules.md](references/plan-rules.md) for itinerary construction rules.

## Workflow

1. Use the local `xiaohongshu-mcp` tools to research the city.
   - Start with `search_feeds` on broad terms such as `城市名 攻略`, `城市名 咖啡`, `城市名 夜市`, `城市名 陶艺`, `城市名 美食`.
   - Drill into the most useful notes with `get_feed_detail`.
2. Extract structured place candidates from the notes.
   - Keep only candidates that look like real POIs or stable districts.
   - Capture source feed IDs, titles, and short reasons.
3. Save the research batch under `imports/xiaohongshu/`.
   - Use `scripts/ingest_xiaohongshu_batch.py`.
4. Promote curated candidates into canonical CityLore places.
   - This reuses `skills/citylore-curator/scripts/ingest_recommendation.py`.
5. Generate the itinerary.
   - Use `scripts/create_travel_plan.py` with city, day count, night count, and optional themes.
   - If the repository has a traveler profile under `data/profiles/<contributor_id>/`, pass `--profile-id` and `--travel-mode` so the plan can inherit late-start, pacing, and nightlife preferences.
   - If the user already knows where they want to stay, pass a lodging anchor such as `--stay-district` or `--stay-name`.
   - If the user wants more than standard tourist highlights, use `--planning-style local`.
6. Return both the database file paths and the human-readable itinerary.

## Research Rules

- Prefer fresh posts and recurring place mentions over one-off viral noise.
- Use multiple queries to cover food, coffee, markets, museums, neighborhoods, and night activities.
- Do not treat every mention as canonical truth. Keep raw research in `imports/xiaohongshu/` even after promotion.
- When the same place appears in multiple notes, merge it into one candidate with richer tags and reasons.

## Commands

Save a normalized Xiaohongshu batch and promote candidates:

```bash
python3 {baseDir}/scripts/ingest_xiaohongshu_batch.py \
  --normalized-file /absolute/path/to/jingdezhen-batch.json \
  --curator-id xhs-city-research \
  --poi-provider amap
```

Generate a 2-day 1-night itinerary:

```bash
python3 {baseDir}/scripts/create_travel_plan.py \
  --plan-id "景德镇4.11 2日游" \
  --city 景德镇 \
  --days 2 \
  --nights 1 \
  --profile-id realRoc \
  --travel-mode companion \
  --stay-district 珠山区 \
  --planning-style local \
  --theme pottery \
  --theme coffee
```

## Notes

- This skill assumes `xiaohongshu-mcp` is already connected and logged in.
- The search step is done through MCP tools, not by shelling out from the Python scripts.
- `ingest_xiaohongshu_batch.py` persists the import batch first, then promotes approved places.
- `create_travel_plan.py` writes both `data/plans/<plan_id>.json` and `data/plans/<plan_id>.md`.
- If you want future revisions to overwrite the same file, pass a fixed `--plan-id`.
- Accommodation constraints only become enforceable once the repository also stores hotel candidates; until then they are preserved as planning notes.
- Even before hotel data exists, the planner can still anchor the trip to a district or commercial area and use that anchor in the plan notes.
- Manually enriched plans may also carry `lodging_recommendations` and `food_recommendations` so the trip file can store concrete hotel choices and specific things to eat alongside the itinerary.
