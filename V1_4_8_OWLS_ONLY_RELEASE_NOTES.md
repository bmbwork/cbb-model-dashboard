# V1.4.8 — Owls-Only Market Data

## Decision

Production market-data acquisition is consolidated onto Owls Insight. There is no dual-provider or parallel-paid-provider mode.

## Added

- `cbb_dashboard/owlsinsight_odds_provider.py`
- Unified NCAAB odds ingestion from Owls Insight.
- Multi-book event coalescing.
- DraftKings reference-line continuity with deterministic fallback.
- Broad, sharp (Pinnacle/Circa), and retail (DraftKings/FanDuel) spread diagnostics.
- Provider freshness, available-book, returned-book, mapping, fallback, and rate-limit health reporting.
- Explicit Admin capture role for `observed`, `open`, `decision`, or `close`.

## Removed

- Production import/use of `OddsApiMarketProvider`.
- `cbb_dashboard/odds_api_provider.py`.
- `tests/test_odds_api_v1_4_2.py`.
- `THE_ODDS_API_*` template secrets.
- Current and historical Odds API Admin controls.

## Preserved

- V1.1.3B forecasting champion.
- Market-blind model firewall.
- Existing Supabase market schema.
- Explicit decision/close provenance and ATS/CLV separation.
- Owner-only raw Owls split archive and public qualitative split commentary.

## Database

No new migration is required.
