# CBB Market Terminal v1.4.5 — Owls Insight Sharp Money

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
