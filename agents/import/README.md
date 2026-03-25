# Import

Prompt or workflow definitions for cold-start ingestion from external platforms.

Recommended workflow for first-party recommendations:

1. Capture the original note or transcript under `imports/manual/raw/`
2. Resolve coordinates only when confidence is acceptable; otherwise keep `coordinates` empty and preserve `address.full_text`
3. Normalize the note into one canonical `place.json` and one contributor-specific opinion file
4. Rebuild `.citylore/exports/` after each successful write

The `skills/citylore-curator/` skill automates this flow.
