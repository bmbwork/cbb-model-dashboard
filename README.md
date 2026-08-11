# CBB Model Dashboard v1.4.3 — Market Terminal / The Odds API + SportsDataIO

Streamlit presentation and downstream market-intelligence layer for the frozen CBB V1.1.3B production champion. Public users remain read-only. Market information never enters the model forecast.

## V1.4.3 highlights

- **The Odds API** remains the sportsbook-line provider.
- **SportsDataIO** is the dedicated public bet % / public money % provider.
- NCAA men's basketball current moneyline, spreads and totals.
- Reference sportsbook line with explicit source provenance.
- Cross-book disagreement and spread-range diagnostics.
- Append-only snapshots for line movement.
- Explicit decision line for ATS and separate closing line for CLV.
- Paid-plan historical backfill with user-selected snapshot role.
- API-credit telemetry in Admin Studio.
- Plain-English bettor interpretation explains crowded public sides, money/ticket disagreement and reverse movement.
- SportsDataIO trial mode is preview-only; production mode publishes verified splits.
- Optional manual/provider-agnostic betting-split imports remain supported.
- Ranked/conference/Saturday/prime-time research context remains separate from V1.1.3B.

## Data boundary

The Odds API supplies sportsbook prices. SportsDataIO supplies public betting splits. V1.4.3 keeps those sources separate and never lets split observations become ATS/closing sportsbook lines. Market data remains downstream of V1.1.3B.

## Database

If the v1.4.2 Market Terminal schema has not already been applied, run the additive/idempotent migration:

`supabase/market_terminal_v1_4_2.sql`

It creates/updates `cbb_market_snapshots` and `cbb_game_context` and leaves `cbb_slates` intact.

## Secrets

Use `STREAMLIT_SECRETS_TEMPLATE.toml`. Use `THE_ODDS_API_KEY` for sportsbook lines and `SPORTSDATAIO_API_KEY` for public splits. Never commit real keys. SportsDataIO defaults to `trial` preview mode.

## Deploy

From the v1.4.3 patch folder:

```bash
bash upgrade_github_v1_4_3.sh
```

The script targets `~/Desktop/cbb-model-dashboard`, requires a clean existing Git clone, pulls `main`, installs the release, validates it, commits and pushes to GitHub.
