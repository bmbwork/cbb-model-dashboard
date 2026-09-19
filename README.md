# CBB Model Dashboard v1.6.0 — Stat Factory UI Polish

V1.6.0 is a **public-interface and slate-discovery release**. The forecasting champion remains frozen at **CBB V1.1.3B**, and sportsbook information remains downstream of the market-blind model.


## Production champion artifact

The frozen **CBB V1.1.3B** production champion runtime is now stored in the private CBB Supabase bucket at:

```text
cbb/production/CBB_V1_1_3B_Champion.zip
```

Verified artifact identity:

```text
size:   15580 bytes
sha256: 9f19e60919a676e842b54093b8d000478a3c228fc8328a6a4c8354abff576452
```

The canonical package contains only the approved frozen champion source/runtime surface required for prediction and grading. Training data, caches, generated predictions, virtual environments, and secret files are excluded. The uploaded object was downloaded again from private Supabase Storage and its SHA-256 was independently reverified after upload.

## Public product structure

The sidebar is intentionally reduced to:

- **Home** — product orientation plus the model/market guide.
- **Today's Board** — the latest published slate with model, sportsbook and market-lifecycle information in one card.
- **Slates by Date** — the main research workbench for selecting historical/published dates and filtering games.
- **Analyst Picks** — the separate human editorial layer.
- **Performance Lab** — historical model evaluation.
- **Admin Studio** — shown only to authorized owner accounts.

The old public Market Terminal, Matchup Explorer, Team Intelligence and standalone Model Guide navigation entries are no longer exposed. Their underlying data/functions are preserved where useful so the change remains reversible.

## v1.6.0 game card

The card keeps CBB's orange/burgundy identity while using a flatter information hierarchy:

1. ML model pick, probability and model fair spread.
2. Best tracked sportsbook spread and moneyline with book attribution.
3. Compact **Open → Current → Close → CLV** market lifecycle.
4. Team projected score and win probability rows, including AP Top 25 badges when available.
5. Validated ticket/money betting splits when available.
6. Three compact secondary model-context metrics.
7. A single expandable **Why this pick?** dossier for deeper matchup context.

Missing market information is shown as unavailable/pending; no sportsbook price or split is fabricated.

## Slates by Date filters

The workbench supports display-only filters for:

- team;
- AP Top 25 / Top 10 / ranked-vs-ranked;
- minimum model win probability;
- best current moneyline on the model pick, with a default example range of **-350 through +500**;
- availability of ML and/or spread markets;
- minimum model-vs-market spread disagreement;
- line movement toward/away from the model pick or movement of at least one point;
- minimum data confidence;
- verified player status;
- Division I-only games;
- neutral/campus venue;
- sorting by model confidence, tip time, AP rank, ML price or spread disagreement.

These filters affect display only. They do not modify a published prediction or become forecasting-model inputs.

## Betting split security

Raw Owl split history and sharp-money diagnostics remain in the service-role-only `cbb_owner_betting_splits` table. V1.6.0 uses a narrow **server-side projection** for public game cards that selects only the latest validated ticket/money percentage fields needed for display. It strips line/sharp fields and forces those rows to observational provenance before attachment, so they cannot become an open, decision or close line.

This design does **not** grant anonymous/authenticated clients direct access to the raw split table and requires no new Supabase migration.

## Market/archive architecture

- **Owls Insight MVP** remains the sole production sportsbook provider.
- `cbb_market_snapshots` preserves explicit `observed`, `open`, `decision`, and `close` roles.
- The v1.5.0 automated best-odds archive remains unchanged.
- ATS grading continues to use the saved decision line.
- CLV continues to use the applicable closing/tracked-close state.
- Sportsbook odds, betting splits and line movement remain downstream decision intelligence.

## Requirements

- Python 3.12
- Existing Supabase market schema through v1.5.0
- Repository virtual environment at `.venv` recommended
- Owls Insight MVP key
- Supabase public/publishable key for public reads
- Supabase secret/server key for Admin Studio and the narrow server-side card split projection

No database migration is required for v1.6.0.

## Relevant Streamlit secrets

```toml
OWLS_INSIGHT_API_KEY = "owlsinsight_..."
SUPABASE_URL = "https://...supabase.co"
SUPABASE_ANON_KEY = "..."
SUPABASE_SECRET_KEY = "..."
```

`SUPABASE_SERVICE_ROLE_KEY` remains supported as the server-key fallback already present in the application.

## Market firewall

Sportsbook odds, consensus, line movement, ticket percentages, handle percentages and sharp-money diagnostics remain downstream. They do not alter CBB V1.1.3B predictions or training.
