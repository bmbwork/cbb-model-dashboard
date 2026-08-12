# CBB Model Dashboard v1.4.8 — Owls Unified Market Data

V1.4.8 consolidates production sportsbook market data and owner-only betting splits onto **Owls Insight**. The forecasting champion remains **V1.1.3B** and remains market-blind.

## What changed

- Owls Insight is now the sole production market-data provider.
- Sportsbook spreads, moneylines, totals, cross-book agreement, and market freshness come from `/api/v1/ncaab/odds`.
- Owner-only ticket/handle splits continue to come from `/api/v1/ncaab/splits`.
- The legacy Odds API adapter, secrets, admin controls, and tests are removed.
- Supabase market provenance is unchanged: `observed`, `open`, `decision`, and `close` remain explicit roles.
- ATS uses an explicit pre-tip `decision` line. CLV uses an explicit pre-tip `close` line. Ordinary observations are never silently promoted.

## Requirements

- Python 3.12
- Existing Supabase Market Terminal schema through v1.4.7
- Active Owls Insight MVP API key in Streamlit Secrets

No new Supabase migration is required for v1.4.8.

## Streamlit Secrets

Required:

```toml
OWLS_INSIGHT_API_KEY = "owlsinsight_..."
```

Optional:

```toml
OWLS_INSIGHT_ODDS_BOOKS = "pinnacle,circa,draftkings,fanduel,betmgm,caesars,bet365,hardrock,westgate,wynn,south_point,stations"
OWLS_INSIGHT_REFERENCE_BOOKMAKER = "draftkings"
```

The old `THE_ODDS_API_*` secrets are no longer read and can be deleted from Streamlit Cloud after deployment.

## Admin Studio workflow

1. Publish/select the model slate.
2. Open **Admin Studio → Market Data**.
3. Choose the capture role:
   - `observed`: normal line-history capture; never grades ATS or CLV.
   - `open`: explicit opening snapshot.
   - `decision`: exact pre-tip line used for ATS grading.
   - `close`: exact pre-tip closing snapshot used for CLV.
4. Click **Refresh Owls sportsbook lines**.
5. Use the existing Owls split controls for owner-only ticket/handle archiving.

## Market firewall

Sportsbook odds, consensus, line movement, ticket percentages, handle percentages, and sharp-money diagnostics remain downstream decision intelligence. They do not alter V1.1.3B predictions.
