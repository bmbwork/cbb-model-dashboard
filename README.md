# CBB Model Dashboard v1.4.6 — Owls Historical Backfill

V1.4.6 keeps the v1.4.5 Owls sharp-money layer and adds an explicit MVP historical split-backfill workflow for completed published slates while keeping the production model market-blind.

## Data roles

- **The Odds API** — sportsbook lines, movement, decision line for ATS, closing line for CLV.
- **Owls Insight** — owner-only DraftKings/Circa ticket and handle percentages.
- **Sharp-money read** — a downstream interpretation of Owls ticket-vs-handle divergence. It is not a production-model feature and it does not prove bettor identity.

## Sharp-money heuristic

For each side, the dashboard calculates `money share - ticket share`.

- under 10 points: no sharp-money flag
- 10–14.9 points: possible signal
- 15–24.9 points: strong signal
- 25+ points: very strong signal
- when the ticket leader and money leader are opposite, the money side is upgraded to at least strong
- agreement across multiple books is labeled a cross-book sharp-money signal
- conflicting book signals are labeled mixed

These are dashboard interpretation thresholds, not Owls Insight provider-defined cutoffs and not predictive model coefficients.

## Install

1. Run `supabase/market_terminal_v1_4_5.sql` once in Supabase SQL Editor.
2. Keep `OWLS_INSIGHT_API_KEY = "owlsinsight_..."` in Streamlit Secrets above `[auth]`.
3. Run `upgrade_github_v1_4_5.sh` from the extracted patch folder.
4. After Streamlit redeploys, sign in and use **Admin Studio → Market Data → Refresh Owls Insight betting splits + sharp money**.

Raw ticket/handle percentages and row-level sharp diagnostics remain owner-only. Public cards receive only qualitative crowd/money/sharp commentary authorized for display.

## V1.4.6 historical split backfill

V1.4.6 adds an explicit MVP historical Owls backfill panel in **Admin Studio → Market Data**. It supports completed published slates such as `2026-02-07`, paginates the historical public-betting archive, stores raw split data owner-only, and optionally refreshes the public non-numeric betting/sharp-money commentary. No new Supabase migration is required.
