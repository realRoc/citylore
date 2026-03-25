# Plan Rules

## General heuristics

- Use at most 4 major stops per day for leisure travel
- Keep day-one evening activities near day-one afternoon areas when possible
- Prefer one signature food stop plus one culture or walk stop each day
- Use coffee or brunch stops as morning fillers
- If a contributor profile says the trip starts late, replace morning-heavy schedules with lunch-first schedules
- If a contributor profile prefers a relaxed pace, keep the day to 2-3 major blocks unless the trip is explicitly compact
- Decide the stay anchor early. If no hotel is fixed yet, lock one district or commercial area first.
- For `local` style trips, prefer real neighborhood life, recurring local food mentions, small galleries, maker spaces, markets, and night atmosphere over checklist attractions.

## Slot model

- `morning`
- `lunch`
- `afternoon`
- `dinner`
- `evening`

For `2 days / 1 night` trips:

- Day 1: `morning`, `lunch`, `afternoon`, `dinner`, `evening`
- Day 2: `morning`, `lunch`, `afternoon`

Profile-aware overrides:

- Late-start companion trips can begin at `lunch`
- Relaxed companion trips should prefer `lunch`, `afternoon`, and `evening`

Stay-anchor heuristics:

- If the user provides a hotel or district, treat it as a hard planning anchor
- If no lodging is fixed, infer the best district from the selected places and evening density
- Prefer staying near the first-night evening zone so the trip remains easy after dinner

## Category hints

- `cafe`, `coffee`, `bakery` -> `morning`
- `food`, `snack`, `restaurant` -> `lunch` or `dinner`
- `museum`, `gallery`, `market`, `attraction`, `park`, `walk` -> `afternoon`
- `night-market`, `bar`, `street`, `district` -> `evening`
