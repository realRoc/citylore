# Data

Canonical local knowledge lives here.

- `areas/` defines geo regions and aliases
- `places/` defines canonical local entities
- `opinions/` stores per-user recommendations and reviews
- `profiles/` stores structured contributor preference context
- `collections/` stores thematic lists
- `plans/` stores reusable itineraries

Recommended file layout:

- `data/areas/<area_id>.json`
- `data/places/<place_id>/place.json`
- `data/opinions/<contributor_id>/<opinion_id>.json`
- `data/profiles/<contributor_id>/profile.json`
- `data/profiles/<contributor_id>/SOUL.md`
