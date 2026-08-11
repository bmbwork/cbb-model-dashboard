# CBB Model Dashboard v1.4.7 — Owls Live Split Archive

This release replaces the unusable NCAAB historical split-backfill workflow with a private history that we build ourselves from live Owls Insight snapshots.

## Install order

1. Run `supabase/market_terminal_v1_4_7.sql` in Supabase SQL Editor.
2. Keep the existing `OWLS_INSIGHT_API_KEY` in Streamlit Secrets.
3. Run `upgrade_github_v1_4_7.sh` from the extracted patch folder.
4. After Streamlit redeploys, open **Admin Studio → Market Data**.

## Admin Studio

For today's NCAAB slate, each successful Owls capture is automatically archived in the private Supabase table. The archive stores raw DraftKings/Circa ticket and handle percentages and the row-level sharp-money diagnostics. Public pages receive only qualitative commentary.

The old **Historical Owls Insight backfill (MVP)** section is removed.

The auto-archive freshness check is session-driven; it is not an unattended background cron service.

## Data firewall

Owls split data remains downstream market context only. It does not feed V1.1.3B. The Odds API remains responsible for actual sportsbook lines, ATS decision lines, and CLV closing lines.
