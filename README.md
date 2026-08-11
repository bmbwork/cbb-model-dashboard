# CBB Model Dashboard v1.4.2 — Market Terminal / The Odds API

Streamlit presentation and downstream market-intelligence layer for the frozen CBB V1.1.3B production champion. Public users remain read-only. Market information never enters the model forecast.

## V1.4.2 highlights

- **The Odds API** is the primary automated sportsbook-line provider.
- NCAA men's basketball current moneyline, spreads and totals.
- Reference sportsbook line with explicit source provenance.
- Cross-book disagreement and spread-range diagnostics.
- Append-only snapshots for line movement.
- Explicit decision line for ATS and separate closing line for CLV.
- Paid-plan historical backfill with user-selected snapshot role.
- API-credit telemetry in Admin Studio.
- Market Terminal works correctly with sportsbook lines even when ticket/money splits are unavailable.
- Optional manual/provider-agnostic betting-split imports remain supported.
- Ranked/conference/Saturday/prime-time research context remains separate from V1.1.3B.

## Data boundary

The Odds API supplies sportsbook odds, not public betting splits. V1.4.2 never invents bet percentages from line movement. Ticket % and money % appear only when an authorized split source is stored separately.

## Database

Run the additive/idempotent migration:

`supabase/market_terminal_v1_4_2.sql`

It creates/updates `cbb_market_snapshots` and `cbb_game_context` and leaves `cbb_slates` intact.

## Secrets

Use `STREAMLIT_SECRETS_TEMPLATE.toml`. The only market credential required for automated lines is `THE_ODDS_API_KEY`. Never commit a real key.

## Deploy

From the v1.4.2 patch folder:

```bash
bash upgrade_github_v1_4_2.sh
```

The script targets `~/Desktop/cbb-model-dashboard`, requires a clean existing Git clone, pulls `main`, installs the release, validates it, commits and pushes to GitHub.
