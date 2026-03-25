# Query

Prompt or workflow definitions for asking location-aware recommendation questions.

Recommended query order:

1. Use `.citylore/exports/catalog.json` for fast filtering by city, district, category, tags, contributor, and text terms
2. Fall back to `data/places/` and `data/opinions/` when the export is stale or richer fields are needed
3. Use coordinates only when the record stores a declared `coord_system`
4. Prefer place-level grouping, then rank with contributor opinion summaries

The `skills/citylore-curator/scripts/query_citylore.py` helper provides a simple CLI for these filters.
