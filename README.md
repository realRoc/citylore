# CityLore

CityLore is an open GitHub-native repository for personal local-life recommendations.

This MVP keeps the source of truth as structured text so contributors can commit, fork, review, and query the data with agents. When the dataset grows, the same structure can be indexed into a database for faster retrieval.

The repository now includes:

- `citylore-curator` for ingesting free-form text notes or audio transcripts into canonical place and opinion records
- `citylore-trip-planner` for researching a city with Xiaohongshu content, promoting curated places into CityLore, and generating itinerary plans

## Core Layers

1. `.citylore/` for node manifest and machine-facing exports
2. `schemas/` for the text data contracts
3. `data/` for canonical areas, places, opinions, profiles, collections, and plans
4. `imports/` for cold-start source ingestion and normalization
5. `relations/` for merge and membership relations
6. `network/` for federation nodes and trust metadata
7. `agents/` for query, import, reconcile, and planning workflows
8. `skills/citylore-curator/` for local recommendation ingestion, coordinate resolution, and export rebuilding
9. `skills/citylore-trip-planner/` for Xiaohongshu research ingestion and itinerary generation

## MVP Rule

The repository is optimized for human-readable text first, machine-queryable structure second, and database indexing later.

## Canonical Write Path

1. Capture the original note under `imports/manual/raw/`
2. Normalize the note into `data/places/` and `data/opinions/`
3. Rebuild `.citylore/exports/` for downstream query tools

## Query Surfaces

- Raw canonical files under `data/`
- Machine-facing exports under `.citylore/exports/`
- Agent workflows under `agents/query/`
- Automation skill under `skills/citylore-curator/`
