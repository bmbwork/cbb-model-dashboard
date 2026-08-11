# CBB Dashboard v1.4.2 — The Odds API Primary

## Summary

V1.4.2 moves the automated Market Terminal line feed to The Odds API while preserving the provider-agnostic market database and the V1.1.3B model firewall.

## Shipped

- The Odds API NCAA men's basketball connector using sport key `basketball_ncaab`.
- Current `h2h`, `spreads` and `totals` refresh.
- Configurable US region or named-bookmaker filter.
- Configurable reference sportsbook, defaulting to DraftKings.
- Reference-book line provenance for ATS grading.
- Cross-book spread count, min/max, range and agreement diagnostics.
- Append-only line history for movement tracking.
- Historical snapshot backfill for paid plans with explicit `open`, `decision`, `close` or `observed` roles.
- API quota telemetry shown to the admin after refresh.
- Market Terminal changed to line-first presentation when no betting splits exist.
- Betting-split fields remain available for a future separate authorized provider/manual import.
- Action Network and Sportradar are no longer wired as automated primary/fallback controls in Admin Studio.
- No production-model inputs or predictions changed.

## Important semantics

The first saved Odds API spread is the site's **tracked opening** unless an explicit historical/manual opener is supplied. It must not be represented as a bookmaker's true market open if collection began later.

The Odds API does not provide ticket or money percentages. V1.4.2 leaves those fields blank instead of treating line movement as a proxy.
