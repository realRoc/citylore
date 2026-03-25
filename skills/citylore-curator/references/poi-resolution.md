# POI Resolution

## Recommended provider order

1. `amap`
   - Best default for mainland China POIs
   - Good address normalization and POI coverage
   - Returns `gcj02` coordinates
2. `nominatim`
   - Good keyless demo and open-data fallback
   - Easier to self-host later
   - Coverage in mainland China is weaker than AMap

## Practical decision rule

- If your main operating area is China mainland, use `amap` in production.
- If you need a zero-cost prototype or self-hosted/open-data path, start with `nominatim`.
- If a provider result is ambiguous, save only the textual address and defer coordinates.

## Provider notes

### amap

- Environment variable: `AMAP_API_KEY`
- Script support: `resolve_coordinates.py --provider amap`
- Best when you have at least `city + place_name`, ideally `district` or address fragments too

### nominatim

- No API key required for light testing
- Script support: `resolve_coordinates.py --provider nominatim`
- Set a meaningful `User-Agent` if you adapt the script for long-running use

## What not to do

- Do not merge different coordinate systems into one field without labeling them.
- Do not treat a fuzzy POI guess as canonical truth.
- Do not overwrite an existing confirmed provider ID with a lower-confidence text match.
