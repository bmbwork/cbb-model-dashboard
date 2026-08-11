# CBB Dashboard v1.4.7 — Owls Live Split Archive

V1.4.7 removes the NCAAB historical public-betting backfill workflow and turns the live Owls feed into our own private, append-only split history.

## What changed

- Removed **Historical Owls Insight backfill (MVP)** from Admin Studio.
- Production code no longer calls `/api/v1/history/public-betting` for NCAAB.
- Current-day Owls split captures use `/api/v1/ncaab/splits` only.
- Every successful live capture automatically writes the raw DraftKings/Circa ticket and handle percentages to `cbb_owner_betting_splits`.
- Persisted owner-only diagnostics now include ticket leader, money leader, sharp side, sharp gap, sharp strength, sharp signal, explanation, diagnostic-rule version, and capture trigger.
- Added a private history viewer/download in Admin Studio.
- Added a 15-minute freshness guard for opportunistic auto-archive on Admin Studio reruns. Manual capture remains available at any time.
- Public pages still receive only qualitative, non-numeric betting commentary.
- The Odds API remains the only sportsbook-line source for ATS/CLV.
- V1.1.3B remains market-blind.

## Sharp-money diagnostic

The stored sharp fields are dashboard-derived diagnostics from ticket-vs-handle divergence. They do not identify bettor identity and are not model inputs.

Current rule version: `ticket_handle_gap_v1`.

- under 10 percentage points: no sharp flag
- 10–14.9: possible
- 15–24.9: strong
- 25+: very strong
- opposite ticket and money leaders upgrades the money side to at least strong
- cross-book agreement is handled downstream in public qualitative commentary

## Required database migration

Run `supabase/market_terminal_v1_4_7.sql` once in Supabase SQL Editor before using the new archive. The migration is idempotent and keeps the raw table service-role only.

## Important scheduling note

The auto-archive control is session-driven: it captures stale data when Admin Studio reruns while the owner is using the site. Streamlit Community Cloud is not being used as an unattended background scheduler in this release.
