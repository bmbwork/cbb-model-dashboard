# CBB Market Terminal v1.4.6 — Owls Historical Backfill

## Streamlit secret

Keep the existing key at top level, above `[auth]`:

```toml
OWLS_INSIGHT_API_KEY = "owlsinsight_YOUR_FULL_KEY"
```

The key is sent only in the `Authorization: Bearer` request header. Never place it in source code, Supabase, URLs, or public HTML.

## Supabase

Run `supabase/market_terminal_v1_4_5.sql` once. It is cumulative and safe if the v1.4.4 migration was already run.

The migration keeps `cbb_owner_betting_splits` private and adds only qualitative sharp-money fields to public `cbb_game_context`:

- `betting_sharp_side`
- `betting_sharp_signal`
- `betting_sharp_confidence`
- `betting_sharp_note`
- `betting_sharp_books`

No raw ticket or handle percentage is added to the public context table.

## Admin workflow

**Admin Studio → Market Data → Refresh Owls Insight betting splits + sharp money**

The owner preview shows the raw ticket/handle percentages plus:

- Sharp Side
- Sharp Gap Pts
- Sharp Strength
- Sharp Signal

`Sharp Gap Pts` is `money share - ticket share` on the flagged side. This is a market-flow diagnostic, not a prediction.

## Public wording

The public site may say things such as:

- “Public heavily on Duke.”
- “Bets and money disagree.”
- “Possible sharp money: North Carolina.”
- “Sharp-money signals from multiple sportsbooks point toward North Carolina.”
- “The model agrees with the sharp-money side.”
- “The model pick conflicts with a strong sharp-money signal.”

Raw percentages remain owner-only.

## V1.4.6 historical Owls backfill

Admin Studio now has a dedicated **Historical Owls Insight backfill (MVP)** panel. Select any completed date that already has a published decision board, then run the backfill. For `2026-02-07`, select that date and click **Backfill historical Owls betting splits**.

The connector requests `/api/v1/history/public-betting` with `sport=ncaab`, identical `startDate`/`endDate`, and paginates in 100-record pages. Raw ticket/handle percentages remain in owner-only storage. The checkbox in the backfill panel controls whether the public qualitative crowd/sharp-money wording is also refreshed.

No new database migration is required beyond `supabase/market_terminal_v1_4_5.sql`.
