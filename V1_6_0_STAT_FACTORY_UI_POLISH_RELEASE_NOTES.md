# CBB Dashboard v1.6.0 — Stat Factory UI Polish

Release date: 2026-09-10

## Purpose

Make the public CBB terminal feel closer to the cleaner Stat Factory / CFB product language without changing the CBB forecasting champion or sportsbook provenance architecture.

## Public navigation

The public sidebar is reduced to five product destinations:

1. Home
2. Today's Board
3. Slates by Date
4. Analyst Picks
5. Performance Lab

Admin Studio remains visible only to the authorized owner account.

Removed from public navigation:

- Market Terminal — its useful sportsbook state is now surfaced directly on Today's Board/game cards.
- Matchup Explorer — date/team discovery is consolidated into Slates by Date.
- Team Intelligence — removed from the public product path.
- Model Guide — folded into Home.

The underlying legacy render functions are not deleted in this release; removing routes rather than destroying code keeps the change reversible.

## Polished CBB game card

The new card retains the orange/burgundy CBB identity but flattens the hierarchy:

- ML PICK + model win probability as the hero.
- Model fair spread shown with the pick rather than in a second oversized hero.
- Four primary comparison tiles: model spread, best spread now, best ML now, model-implied odds.
- Compact market lifecycle line: Open → Current → Close → CLV plus direction of spread movement.
- Compact away/home rows show projected score and win probability.
- AP Top 25 rank badges display when context is available.
- Betting splits show directly on the card when a validated Owls snapshot exists.
- Secondary metrics are reduced to projected total, pace and data confidence.
- One expandable Why this pick? dossier retains the deeper matchup, sportsbook and glossary content without repeating a second market-pulse block.

No synthetic sportsbook price, line, split, opener or close is created when a field is unavailable.

## Slates by Date

Slates by Date is now the main discovery/research tool. It supports:

- slate date selection;
- team filter;
- AP Top 25, AP Top 10 and ranked-vs-ranked filters;
- minimum model win probability;
- best current ML range on the model's straight-up pick (default example -350 through +500);
- sportsbook availability (ML, spread, or both);
- minimum model-vs-market spread disagreement;
- line movement toward/away from the model pick or 1+ point movement;
- minimum data confidence;
- verified player-status only;
- Division I only;
- neutral/campus venue filter;
- sort by model win chance, tip time, AP rank, best ML or spread disagreement;
- card or compact table result views.

Every filter is display-only and leaves the frozen prediction unchanged.

## Public betting-split projection

The raw `cbb_owner_betting_splits` table remains private/service-role-only. v1.6.0 adds a narrow Streamlit server-side read projection that selects only the public card fields:

- game/market identity;
- timestamp/source label;
- ticket percentages;
- money/handle percentages.

Line fields, sharp-money diagnostics and internal raw metadata are not selected. Projected rows are forcibly treated as `observed`, so they cannot become open, decision or close lines. No Supabase RLS policy is relaxed and no SQL migration is required.

The card suppresses 0/0 split sentinels instead of presenting them as real market data, including the away-side complement case.

## Performance changes

Board + market/archive queries now run only for Today's Board and Slates by Date. Home, Analyst Picks, Performance Lab and Admin Studio no longer force the public board/archive render path on every rerun.

## Forecasting and market invariants preserved

Unchanged:

- CBB V1.1.3B remains frozen.
- Forecasting remains market-blind.
- Owls Insight remains the sole production sportsbook provider.
- The v1.5.0 hourly best-odds archive remains intact.
- Decision line remains distinct from observed/open/close.
- ATS grading does not use closing lines retroactively.
- CLV remains downstream market evaluation.
- No model coefficients, model package, calibration artifact or historical model output are modified.

## Files added

- `cbb_dashboard/board_filters.py`
- `tests/test_ui_polish_v1_6_0.py`
- `V1_6_0_STAT_FACTORY_UI_POLISH_RELEASE_NOTES.md`
- `VALIDATION_REPORT_V1_6_0.md`

## Files materially changed

- `app.py`
- `cbb_dashboard/intelligence.py`
- `cbb_dashboard/ui.py`
- `cbb_dashboard/storage.py`
- `README.md`
- `PROJECT_MANIFEST.txt`
- selected regression tests updated for the v1.6.0 public navigation/version contract.

## Database changes

None.

## Configuration changes

No new secret names are introduced. To display card-level numeric betting splits, the existing Streamlit server key (`SUPABASE_SECRET_KEY` or supported `SUPABASE_SERVICE_ROLE_KEY` fallback) must be configured because the raw split table intentionally remains inaccessible to anon/authenticated clients.
