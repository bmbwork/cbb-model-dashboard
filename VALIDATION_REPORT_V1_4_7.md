# Validation Report — CBB Dashboard v1.4.7

Validation performed on the reconstructed v1.4.6 website with the v1.4.7 changes applied.

## Automated tests

- Result: **112 passed**
- Command: `PYTHONPATH=. pytest -q`
- Python compilation: passed for `app.py` and all `cbb_dashboard/*.py` modules.

## Covered behavior

- Owls Bearer-key handling remains server-side.
- Live NCAAB split parser preserves per-book DraftKings/Circa ticket and handle percentages.
- Ticket leader, money leader, sharp side, gap, strength, signal, and read persist through database record serialization and history-frame deserialization.
- Private Supabase migration retains RLS and explicitly revokes `anon`/`authenticated` access.
- Historical Owls NCAAB public-betting backfill controls are removed from Admin Studio.
- Production Owls provider no longer calls `/api/v1/history/public-betting`.
- Live capture and opportunistic 15-minute archive freshness controls are present.
- Existing public percentage-leakage protections remain.
- The Odds API line-provider role and ATS/CLV provenance tests remain intact.
- V1.1.3B market firewall remains intact.
