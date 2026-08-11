# Validation Report — CBB Dashboard v1.4.6

## Result

- Python compilation: passed
- Full automated regression suite: **110 passed / 110 total**
- Historical pagination test: passed for a synthetic 137-record Saturday archive (100 + 37)
- Historical request contract: passed for `sport=ncaab`, identical `startDate`/`endDate`, `limit=100`, and offset pagination
- Stable historical timestamp fallback: passed
- Explicit Admin Studio historical backfill UI: passed
- Existing owner-only raw split privacy: regression passed
- Existing public qualitative commentary / no raw percentage leakage: regression passed
- Existing sharp-money diagnostics: regression passed
- The Odds API ATS/CLV provenance separation: regression passed
- V1.1.3B market firewall: regression passed

## Database

No new Supabase migration is required. V1.4.6 reuses the owner-only Owls split table and public qualitative context fields created by the v1.4.5 migration.
