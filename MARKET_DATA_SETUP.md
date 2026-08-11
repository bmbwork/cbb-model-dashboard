# CBB Market Terminal v1.4.3 — The Odds API + SportsDataIO

## Provider split

V1.4.3 uses two downstream market providers with different jobs:

- **The Odds API** supplies actual sportsbook lines, prices, cross-book spread ranges and line movement.
- **SportsDataIO** supplies public bet percentage and public money percentage.

Neither provider changes the V1.1.3B forecast.

## Streamlit Secrets

Keep all market secrets above the `[auth]` section:

```toml
THE_ODDS_API_KEY = "..."
THE_ODDS_API_REGIONS = "us"
THE_ODDS_API_BOOKMAKERS = ""
THE_ODDS_API_REFERENCE_BOOKMAKER = "draftkings"

SPORTSDATAIO_API_KEY = "..."
SPORTSDATAIO_SPLITS_MODE = "trial"
```

`SPORTSDATAIO_SPLITS_MODE` values:

- `trial` — fetch and preview in Admin Studio only; nothing is published publicly.
- `production` — publish SportsDataIO split history to the Market Terminal.

Use production only after SportsDataIO confirms the split percentages in the account are production/unscrambled and licensed for the intended display.

## SportsDataIO refresh

Admin Studio -> Market Data -> **Refresh SportsDataIO public betting splits**.

The connector:

1. calls `GameOddsByDate/{date}` to map the published CBB slate to SportsDataIO GameIDs;
2. calls `BettingSplitsByGameId/{gameId}` for each mapped game;
3. uses `BettingMetadata` as an enum-label fallback;
4. stores spread, moneyline and total split history as `observed` snapshots;
5. never writes sportsbook lines from SportsDataIO into the ATS/CLV line fields.

## Historical slates

The split-by-game endpoint returns split movement/history for the game, so the same SportsDataIO refresh button can populate historical split observations when the account entitlement exposes those games.

## ATS / CLV provenance

- `observed` = market observation only.
- `open` = explicit opener.
- `decision` = the saved pregame line eligible for ATS grading.
- `close` = closing line used separately for CLV.

V1.4.3 does not infer decision or closing lines from ordinary observations.

## Public interpretation

The Market Pulse translates the feed into plain English:

- Public Bets = share of betting tickets.
- Public Money = share of dollars wagered.
- If tickets and money disagree, the card explains which team has more bets and which team has more dollars.
- If the line moves against the popular side, the card explains that the market is not following the crowd.
- The copy may note when the model agrees with the money side or disagrees with both the public and the money.

The site does not label these patterns “sharp money” and does not automatically call them profitable bets.
