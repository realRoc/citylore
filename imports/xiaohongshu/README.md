# Xiaohongshu

Import flow:

1. `raw/` for source snapshots
2. `normalized/` for structured extraction
3. `candidates/` for reviewable place candidates
4. `mappings/` for links to canonical place IDs

Recommended batch files:

- `raw/<batch_id>.json` for the raw search or detail payloads collected from `xiaohongshu-mcp`
- `normalized/<batch_id>.json` for extracted feed summaries and place candidate arrays
- `candidates/<batch_id>.json` for deduped city POI candidates
- `mappings/<batch_id>.json` for the promoted `candidate -> place_id` map
