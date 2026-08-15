# CBB Betting Intelligence v1.5.0 — Automated Best-Odds Historical Archive

## Purpose

Create a permanent first-party sportsbook history using Owls Insight as the sole market provider.

## New capability

- Archives every available pregame NCAAB event independently of model-board publication.
- Captures best available spread and moneyline for both teams across returned sportsbooks.
- Preserves sportsbook identity and price for each best quote.
- Retains the complete returned per-book quote set in compact JSON on every hourly market record, so future sharp/retail/consensus research can be reconstructed instead of being discarded.
- First observed quote is tracked as `open`.
- Hourly observations build line-movement history.
- The final actually stored pregame hourly quote becomes the tracked `close`; if the hourly run falls within 25 minutes of tip it is marked immediately, otherwise the next run finalizes that last pregame quote.
- A missed scheduler close is finalized from the last actually stored pregame observation; no price is fabricated.
- Team/game cards display current best spread/ML, tracked opening line, movement, tracked close and best-market CLV when an explicit decision line exists.

## Model firewall

V1.1.3B is unchanged. The archive is downstream market intelligence and never enters the forecasting feature matrix.

## ATS/CLV provenance

Existing `cbb_market_snapshots` decision-line grading remains unchanged. ATS continues to grade against the explicit `decision` line. The automated archive is a separate historical feed and provides best-market open/current/close context.

## Infrastructure

Adds:

- `cbb_owls_best_odds_archive` (full hourly history)
- `cbb_owls_best_odds_card_state` (lightweight open/current/close view)
- `scripts/archive_owls_best_odds.py`
- `.github/workflows/cbb_owls_best_odds_archive.yml`
- `cbb_dashboard/best_odds_archive.py`

Python deployment target remains 3.12.

## Corrective installer hardening

The final v1.5.0 patch also cleans up legacy test residue from provider integrations that were retired before the Owls-only baseline. The obsolete Action Network provider test is removed, while the older market-terminal test keeps its generic provenance coverage but drops Sportradar-specific imports/tests for a module that no longer exists. The installer now prefers the repository's Python 3.12 `.venv` for validation.

### Final installer correction

A second validation failure was traced to ignored Python bytecode left by a previous rolled-back run. Git does not remove ignored `__pycache__` / `.pyc` files during a normal reset, and the earlier retired-provider guard recursively scanned those binary artifacts after compilation. The final installer now:

- purges generated Python/test bytecode caches before validation while preserving `.venv`;
- scans only `tests/**/*.py` source for retired provider imports/usages;
- scans only active Python/YAML production source for legacy Odds API references;
- reconciles historical tests that still pointed at removed SQL migration filenames (`market_terminal_v1_4.sql` and `market_terminal_v1_4_4.sql`) to their present superseding migrations;
- updates stale current-version assertions to v1.5.0;
- updates historical line-provider assertions to the Owls-only v1.4.8 contract.

This preserves the useful ATS, decision/close provenance, post-tip protection, RLS/security, and model-firewall regression coverage rather than deleting the historical suite wholesale.
