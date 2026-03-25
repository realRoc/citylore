---
name: citylore-curator
description: Ingest personal city-life recommendations into the CityLore repository. Use when the user provides a text note, transcript, or audio file about a place and wants it normalized into canonical place and opinion records, optionally with resolved coordinates and rebuilt query exports.
metadata:
  openclaw:
    emoji: "🏙️"
    requires:
      bins: ["python3"]
---

# CityLore Curator

## Overview

Use this skill to turn a free-form recommendation into CityLore data. It captures the original note, creates or updates a canonical place, writes a contributor-specific opinion, and rebuilds machine-facing exports for later query.

Read [references/data-model.md](references/data-model.md) when you need the exact storage layout. Read [references/poi-resolution.md](references/poi-resolution.md) when the user asks how to obtain offline coordinates or which provider to use.

## Workflow

1. Identify the source form.
   - Text note: use the note directly as source text.
   - Audio file: transcribe it first with local `whisper` when available, or with another transcription workflow, then continue.
2. Extract the minimum canonical fields before writing:
   - `contributor_id`
   - `place_name`
   - `city`
   - recommendation `body`
   - Optional but useful: `district`, `address`, `category`, `tags`, `rating`, `visit_date`
3. Resolve coordinates only if confidence is acceptable.
   - If the user gave an exact address or a high-confidence POI match, use `scripts/resolve_coordinates.py`.
   - If not, keep `coordinates` empty and preserve the free-form address.
4. Ingest the record with `scripts/ingest_recommendation.py`.
5. Rebuild exports with `scripts/rebuild_exports.py` if the ingest command did not already do it.
6. Report the created or updated files back to the user.

## Coordinate Rules

- Prefer provider-native coordinates with an explicit `coord_system`.
- Do not silently mix `gcj02`, `bd09`, and `wgs84`.
- For mainland China POIs, default to `amap` when available.
- For a keyless demo or non-China coverage, use `nominatim`.
- If no confident result is found, store only `address.full_text`.

## Commands

Resolve coordinates:

```bash
python3 {baseDir}/scripts/resolve_coordinates.py \
  --query "上海 愚园路 某某咖啡" \
  --provider amap
```

Ingest a text recommendation:

```bash
python3 {baseDir}/scripts/ingest_recommendation.py \
  --contributor-id roc \
  --place-name "某某咖啡" \
  --city "上海" \
  --district "静安区" \
  --category cafe \
  --tag coffee \
  --tag quiet \
  --body "适合工作日下午去，手冲稳定，插座够用，但高峰期偏吵。" \
  --text "这家店适合工作日下午去，手冲稳定，插座够用，但高峰期偏吵。" \
  --resolve-coordinates \
  --poi-provider amap
```

Ingest from audio while preserving the transcript:

```bash
python3 {baseDir}/scripts/ingest_recommendation.py \
  --contributor-id roc \
  --place-name "某某咖啡" \
  --city "上海" \
  --body "适合单人办公，咖啡豆新鲜。" \
  --audio-file /absolute/path/to/note.m4a \
  --source-kind audio
```

Query the repository later:

```bash
python3 {baseDir}/scripts/query_citylore.py --city 上海 --tag coffee --text 安静
python3 {baseDir}/scripts/query_citylore.py --near-lat 31.224 --near-lng 121.444 --radius-km 2
```

## Notes

- `baseDir` is the skill directory.
- The scripts auto-detect the CityLore repo root by walking upward to `.citylore/manifest.yaml`.
- `ingest_recommendation.py` rebuilds exports after a successful write.
- Audio transcription uses the local `whisper` CLI only when it is already installed.
