<!-- STAT_FACTORY_EMERGENCY_MAINTAINER -->
> **CBB INTELLIGENCE — EMERGENCY MAINTAINER NOTES — updated 2026-09-23**
>
> Repository: `bmbwork/cbb-model-dashboard`  
> Production champion: **CBB V1.1.3B**  
> Supabase project: `mtiwegegbmheefqombrw`  
> Streamlit entrypoint: `app.py`  
> Live dashboard: `https://cbb-model-dashboard.streamlit.app/`
>
> **Before editing production:** verify current `main`, current production health, the latest successful production workflow, and the relevant production handoff/manifest. Research branches, experiment folders, archived release notes, and UI version numbers do not promote a model by themselves.

## Emergency maintainer context

- Dashboard/UI release numbers such as v1.6.0 are not model versions. The forecasting champion remains CBB V1.1.3B.
- Champion artifact: cbb/production/CBB_V1_1_3B_Champion.zip; SHA-256 9f19e60919a676e842b54093b8d000478a3c228fc8328a6a4c8354abff576452.
- Owl sportsbook information, splits, line movement, CLV, and analyst picks are downstream and must not alter the frozen forecast.
- CBB is seasonal; offseason idle health is not automatically an incident.
- The health Edge Function should prefer a modern Supabase secret key before the legacy service-role JWT fallback.

### Files to inspect first

- `docs/PRODUCTION_HANDOFF.md` — champion/artifact handoff
- `app.py` — Streamlit entrypoint
- `stat_factory_access.py` — parent access wall
- `cbb_dashboard/` — dashboard/domain code
- `supabase/schema.sql` — database contract
- `supabase/functions/stat-factory-health/index.ts` — parent health contract
- `.github/workflows/game_board_ci.yml` — board QA
- `.github/workflows/production_health.yml` — health
- `.github/workflows/cbb_owls_best_odds_archive.yml` — market archive
- `.github/workflows/progressive_grading.yml` — grading

### Non-negotiable production rules

- Preserve the market-blind model / downstream sportsbook firewall.
- Preserve immutable published forecast revisions and provenance.
- Do not fabricate missing sportsbook prices, splits, probabilities, injuries, lineups, or model outputs.
- Do not expose Supabase secret/service-role keys, Owl credentials, Streamlit secrets, or admin credentials.
- The direct Streamlit URL is **not** an authorization mechanism. Production must call the repository's `stat_factory_access` gate before protected content loads.
- A model change is not a production promotion until evidence is reviewed and the production designation is explicitly updated.
- Prefer the smallest reversible repair, run repository QA/CI, and verify live behavior after deployment.
- See `supabase/README.md` for database/Edge Function notes; if it is absent, create/read the infrastructure handoff before changing Supabase.

---

<!-- STAT_FACTORY_AUTHORITATIVE_MAINTAINER_V1 -->
> ## Stat Factory authoritative maintainer notes — 2026-09-23
>
> **Product:** CBB Intelligence  
> **Production champion:** **CBB V1.1.3B**  
> **Repository:** `bmbwork/cbb-model-dashboard`  
> **Supabase project:** `mtiwegegbmheefqombrw`  
> **Streamlit entrypoint:** `app.py`  
> **Production dashboard:** `https://cbb-model-dashboard.streamlit.app/`  
> **Parent product key:** `cbb`
>
> If any older section, archived document, experiment folder, or branch conflicts with these notes, verify live production state before editing. The root README plus the verified production handoff/model manifest is authoritative; newer-looking research is not automatically production.

### Maintainer: read these first
- `app.py` — Streamlit entrypoint.
- `stat_factory_access.py` — membership wall.
- `docs/PRODUCTION_HANDOFF.md` — champion package identity.
- `supabase/README.md` — production Supabase project, security and incident guide.
- `supabase/schema.sql` — database contract.
- `supabase/functions/stat-factory-health/index.ts` — child health function.
- `AUTOMATION.md` — production automation notes.

### Current workflow map
- `.github/workflows/cbb_owls_best_odds_archive.yml`
- `.github/workflows/production_health.yml`
- `.github/workflows/progressive_grading.yml`
- `.github/workflows/public_consensus_hourly.yml`
- `.github/workflows/analyst_feed_ci.yml`
- `.github/workflows/automation_regression.yml`
- `.github/workflows/display_regression.yml`
- `.github/workflows/game_board_ci.yml`

### Do-not-break rules
- Dashboard/UI version numbers are not the forecasting-model version. The champion remains V1.1.3B.
- The champion package SHA-256 is `9f19e60919a676e842b54093b8d000478a3c228fc8328a6a4c8354abff576452`.
- Odds, splits, line movement and CLV are downstream and must never rewrite V1.1.3B forecasts.
- Modern Supabase secret keys should be preferred before legacy service-role JWT fallback in health/server code.
- Owl/sportsbook information remains downstream from the market-blind production forecast unless a separately named research model explicitly says otherwise.
- Keep secrets server-side. Never commit Supabase secret/service-role keys, Owl credentials, admin credentials, or Streamlit secrets.
- `stat_factory_access.py` (or the dashboard-local equivalent) must run before protected terminal data renders. A raw Streamlit URL must not bypass the Stat Factory entitlement wall.
- Preserve immutable forecast revisions and provenance. Do not edit historical predictions in place to match later outcomes or market moves.
- Before production changes: verify model version -> inspect recent workflows/health -> make the smallest reversible change -> run tests/CI -> verify live behavior.

### If the owner is unavailable
1. Do not promote or replace a model first.
2. Inspect recent GitHub Actions and the production health endpoint.
3. Confirm the current board/model version in Supabase.
4. Separate model problems from market-feed, database, access-gate, and UI problems.
5. Do not delete production tables, buckets, migrations, secrets, or artifacts as a troubleshooting shortcut.
6. Record any manual production action and its reason.
7. For cross-product identity, billing, entitlements and launch behavior, consult `bmbwork/Stat-Factory`.

---

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
