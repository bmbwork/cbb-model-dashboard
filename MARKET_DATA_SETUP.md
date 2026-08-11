# CBB Market Terminal v1.4.2 — The Odds API Setup

## Primary source

V1.4.2 uses **The Odds API** as the primary automated sportsbook-line provider for NCAA men's basketball. It supplies current and historical bookmaker prices for moneyline, spreads and totals. The production V1.1.3B model remains completely market-blind.

The Odds API does **not** provide public ticket-share or money/handle-share betting splits. Those fields remain optional and can be populated later from a separate authorized source or manual import without changing the database contract.

## Streamlit Secrets

Add the following to Streamlit Community Cloud -> App settings -> Secrets:

```toml
THE_ODDS_API_KEY = "..."
THE_ODDS_API_REGIONS = "us"
THE_ODDS_API_BOOKMAKERS = ""
THE_ODDS_API_REFERENCE_BOOKMAKER = "draftkings"
```

`THE_ODDS_API_BOOKMAKERS` is optional. When populated it takes precedence over `THE_ODDS_API_REGIONS`. The reference bookmaker is the named sportsbook whose actual line is used for the game-level display and ATS provenance when available. Cross-book lines are used only for disagreement/range diagnostics.

## Current refresh

Admin Studio -> Market Data -> **Refresh The Odds API market lines** queries `basketball_ncaab` for `h2h`, `spreads` and `totals` in American odds format.

For every mapped game, the adapter stores:

- reference-book spread and price;
- reference-book moneyline;
- reference-book total and prices;
- number of sportsbooks with a spread;
- minimum/maximum home spread across books;
- cross-book spread range and agreement label;
- provider event id and source sportsbook;
- provider update timestamp;
- API quota headers returned by The Odds API.

Repeated refreshes build the line-movement history. The first saved spread acts as the tracked opening line unless an explicit `open` historical/manual snapshot is stored.

## Historical backfill

Paid The Odds API plans expose historical featured-market snapshots. Admin Studio includes a historical snapshot tool that accepts an ISO UTC timestamp and one of four roles:

- `observed`
- `open`
- `decision`
- `close`

Historical featured-market requests cost 10 times the normal market/region credit rate. The UI therefore makes historical pulls explicit rather than running them automatically.

Use `decision` only for a line that represents the pregame number available at the model/bet-decision point. Use `close` only for a last valid pregame line. ATS grading uses the decision/taken line; the closing line is separate for CLV.

## Bet splits

The Odds API does not supply ticket % or money %. V1.4.2 does not infer or fabricate them from line movement. The Market Terminal clearly labels these as unavailable unless a separate authorized split feed/import is published.

The existing CSV market-import path remains available for future licensed splits data. It writes to the same provider-agnostic snapshot table.

## Cost controls

For the standard current endpoint, The Odds API charges by requested market x region. The default configuration requests three featured markets in one region. The admin success message shows the API response headers for credits used, credits remaining and last-request cost.

Historical featured-market snapshots use the documented 10x multiplier and are never auto-polled.

## Security

The API key is read only from Streamlit Secrets and never written into Supabase, HTML, logs, exported CSVs or the Git repository. Public users have no refresh controls.
