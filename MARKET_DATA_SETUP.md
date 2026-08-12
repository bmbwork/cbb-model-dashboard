# Market Data Setup — v1.4.8

## Provider architecture

**Owls Insight is the sole production market-data provider.**

- `/api/v1/ncaab/odds`: spreads, moneylines, totals, sportsbook comparison, freshness.
- `/api/v1/ncaab/splits`: owner-only DraftKings/Circa ticket and handle splits.
- Supabase: permanent archive for observed, opening, decision, closing, and private split snapshots.

The V1.1.3B forecast remains independent of all market data.

## Required secret

```toml
OWLS_INSIGHT_API_KEY = "owlsinsight_..."
```

Optional controls:

```toml
OWLS_INSIGHT_ODDS_BOOKS = "pinnacle,circa,draftkings,fanduel,betmgm,caesars,bet365,hardrock,westgate,wynn,south_point,stations"
OWLS_INSIGHT_REFERENCE_BOOKMAKER = "draftkings"
```

DraftKings remains the default reference sportsbook for continuity with existing ATS decision-line history. When unavailable, the adapter uses a deterministic named-book fallback and preserves the actual sportsbook in `Source Label`.

## Supabase

No v1.4.8 migration is required. Keep the existing Market Terminal schema through `supabase/market_terminal_v1_4_7.sql`.

The existing provenance contract remains authoritative:

- `observed`: history/line movement only.
- `open`: explicit opener.
- `decision`: explicit pre-tip line for ATS grading.
- `close`: explicit pre-tip line for CLV.

A normal `observed` row is never promoted to `decision` or `close` automatically.

## Cross-book diagnostics

For spread rows the Owls adapter stores:

- reference sportsbook line and price,
- book count,
- minimum/maximum home spread,
- spread range and agreement label,
- broad median home spread,
- sharp median from Pinnacle/Circa when available,
- retail median from DraftKings/FanDuel when available.

These diagnostics are market context only and are not forecasting features.

## Historical data

V1.4.8 intentionally removes the former external historical-snapshot control from the production Admin workflow. Forward market history is captured permanently in Supabase using explicit roles. Owls MVP historical endpoints can be added later as a dedicated research/backfill workflow after NCAAB coverage is validated; they are not required for routine ATS/CLV provenance.

## Security

Do not place the API key in source code, URLs, CSV exports, or public Supabase tables. The app sends it only in the Owls Insight Bearer authorization header.
