# Market Data Setup — v1.4.7

## Provider roles

- **The Odds API**: actual sportsbook spreads, moneylines, totals, line movement, ATS decision lines, and CLV close lines.
- **Owls Insight**: current NCAAB DraftKings/Circa ticket and handle splits for owner-only market intelligence.
- **Supabase private archive**: permanent history of Owls snapshots captured live by this dashboard.

The prediction engine remains independent of all market data.

## Secrets

Keep the existing top-level Streamlit secret:

```toml
OWLS_INSIGHT_API_KEY = "owlsinsight_..."
```

Do not place API keys in source code, URLs, CSV exports, or public Supabase tables.

## Required migration

Run:

`supabase/market_terminal_v1_4_7.sql`

The private `cbb_owner_betting_splits` table remains inaccessible to `anon` and `authenticated` roles. V1.4.7 adds persisted diagnostic columns and an archive index.

## Admin workflow

For the current Eastern Time slate, Admin Studio provides:

- **Auto-archive stale live splits on Admin Studio refresh** — if the latest private write is at least 15 minutes old, a page rerun captures a new snapshot.
- **Capture live Owls betting splits now** — force a live capture immediately.
- **Private Owls split history** — view or download all stored snapshots for the selected slate.

Past slates do not call Owls historical public-betting backfill. They show only snapshots that were captured live and stored in our own archive.

## Stored private fields

For each sportsbook/market/timestamp, the archive stores raw ticket and handle percentages plus:

- Ticket Leader
- Money Leader
- Sharp Side
- Sharp Gap Pts
- Sharp Strength
- Sharp Signal
- Sharp Read
- Sharp Rule Version
- Capture Trigger

Public cards do not expose raw percentages.
