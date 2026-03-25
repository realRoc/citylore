# Planning

Prompt or workflow definitions for building local-life plans from places, opinions, and profiles.

Recommended itinerary workflow:

1. Research the city with first-party notes or imported sources such as Xiaohongshu
2. Normalize high-confidence places into `data/places/`
3. Rank places by city, district, category, tags, and opinion density
4. Apply profile defaults from `data/profiles/<contributor_id>/profile.json` and `SOUL.md` when available
5. Build one `data/plans/<plan_id>.json` plus a companion markdown itinerary

The `skills/citylore-trip-planner/` skill automates this flow and can start from `imports/xiaohongshu/`.
