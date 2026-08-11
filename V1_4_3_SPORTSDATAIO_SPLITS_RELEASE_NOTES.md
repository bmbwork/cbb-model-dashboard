# CBB Dashboard v1.4.3 — SportsDataIO Public Betting Splits

## Purpose

V1.4.3 adds SportsDataIO as the dedicated public-betting-splits provider while keeping The Odds API as the sportsbook-line provider. V1.1.3B remains market-blind.

## Provider responsibilities

- **The Odds API:** sportsbook spread, moneyline, total, cross-book agreement, line movement, decision line, closing line, ATS provenance, CLV.
- **SportsDataIO:** public bet percentage and public money percentage for spread, moneyline and total markets, including split history returned by the game-level split endpoint.

The two feeds are merged at the presentation/research layer. SportsDataIO split rows never overwrite The Odds API sportsbook line rows.

## SportsDataIO endpoints

The connector uses the documented NCAA basketball endpoints:

- `GameOddsByDate/{date}` — resolves SportsDataIO GameIDs for the selected slate.
- `BettingSplitsByGameId/{gameId}` — retrieves public bet/money split history for the mapped game.
- `BettingMetadata` — maps betting enum IDs when labels are not included directly in the split payload.

Authentication uses the `Ocp-Apim-Subscription-Key` request header. The key is never put in a URL, persisted to Supabase or emitted into HTML.

## Secrets

```toml
SPORTSDATAIO_API_KEY = "..."
SPORTSDATAIO_SPLITS_MODE = "trial"
```

`trial` is preview-only. Split percentages are not published to the public board. Change the mode to `production` only after SportsDataIO confirms the entitlement is suitable for real public betting percentages.

## Plain-English bettor interpretation

Game cards now translate split behavior into ordinary language. Examples:

- **Crowded public side:** “The crowd and the money both favor Duke: 72% of bets and 68% of the money are on that side.”
- **Public-heavy but weaker money:** “Duke has 76% of the bets but only 58% of the money. A lot of people are betting Duke, but the dollars are less convinced.”
- **Money/bet disagreement:** “Most bets are on Purdue (63%), but most of the money is on Michigan (64%). Fewer bets are backing Michigan, but those bets represent more dollars.”
- **Reverse movement:** “The line is moving away from the popular side and toward Michigan. Bettors watch this because the sportsbook market is not following the crowd.”
- **Model agrees with money, not crowd:** “The model is also on Michigan, so the model agrees with the money side rather than the more popular side.”

The UI intentionally does not call larger-bet signals “sharp money” and does not convert market agreement into an automatic BET/LEAN/+EV recommendation.

## Data-provenance correction

V1.4.3 also closes the observed/decision/close role leak found during the first historical backfill:

- `observed` remains an observation only.
- only explicit `decision` snapshots can grade ATS.
- only explicit `close` snapshots can populate the closing line / CLV reference.
- split observations are always `observed` and can never become an ATS line.

## Database

No new Supabase migration is required if `market_terminal_v1_4_2.sql` has already been applied. The provider-agnostic snapshot table already contains the ticket/money percentage fields required by SportsDataIO.
