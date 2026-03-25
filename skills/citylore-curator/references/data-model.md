# CityLore Data Model

## Canonical write targets

- `imports/manual/raw/<timestamp>-<id>.md`
- `data/areas/<area_id>.json`
- `data/places/<place_id>/place.json`
- `data/opinions/<contributor_id>/<opinion_id>.json`
- `.citylore/exports/catalog.json`
- `.citylore/exports/places.ndjson`
- `.citylore/exports/opinions.ndjson`

## Minimal required fields

### place.json

- `place_id`
- `name`
- `country`
- `city`
- `category`
- `tags`
- `source_refs`
- `created_at`
- `updated_at`

### opinion.json

- `opinion_id`
- `place_id`
- `contributor_id`
- `source_kind`
- `source_ref`
- `body`
- `tags`
- `created_at`
- `updated_at`

## Query-oriented fields

- `place.city`
- `place.district`
- `place.category`
- `place.tags`
- `place.coordinates`
- `opinion.summary`
- `opinion.tags`
- `opinion.signals.good_for`
- `opinion.signals.avoid_if`

## Identity rules

- Canonical places should be reused when `provider_place_id` matches or when the same `place_name + city + district` match is confident.
- Opinions stay contributor-specific and append-only.
- Keep the raw source path in both `place.source_refs` and `opinion.source_ref` for provenance.

## Coordinate rules

- Store coordinates only with a declared `coord_system`.
- Keep the provider-native coordinate system instead of forcing silent conversion during ingest.
- For China providers this usually means `gcj02`; for Nominatim this usually means `wgs84`.
