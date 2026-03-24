# CityLore

CityLore is an open GitHub-native repository for personal local-life recommendations.

This MVP keeps the source of truth as structured text so contributors can commit, fork, review, and query the data with agents. When the dataset grows, the same structure can be indexed into a database for faster retrieval.

## Core Layers

1. `.citylore/` for node manifest and machine-facing exports
2. `schemas/` for the text data contracts
3. `data/` for canonical areas, places, opinions, profiles, collections, and plans
4. `imports/` for cold-start source ingestion and normalization
5. `relations/` for merge and membership relations
6. `network/` for federation nodes and trust metadata
7. `agents/` for query, import, reconcile, and planning workflows

## MVP Rule

The repository is optimized for human-readable text first, machine-queryable structure second, and database indexing later.
