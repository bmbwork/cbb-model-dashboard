# v1.5.0 Automated Owls Best-Odds Archive — One-Time Setup

The code release is automated after these two one-time infrastructure steps.

## 1. Create the Supabase archive table

Open Supabase -> SQL Editor and run:

`supabase/market_archive_v1_5.sql`

This creates `public.cbb_owls_best_odds_archive`, enables public read access for the dashboard, and reserves writes for the service-role/secret key.

## 2. Add GitHub Actions repository secrets

GitHub -> `bmbwork/cbb-model-dashboard` -> Settings -> Secrets and variables -> Actions -> New repository secret.

Create:

- `OWLS_INSIGHT_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`

Use the same Owls API key and Supabase project/secret values already used by the production deployment. Do not commit them to the repository.

## 3. Add the season activation variable

GitHub -> Settings -> Secrets and variables -> Actions -> **Variables**.

Create `CBB_ODDS_ARCHIVE_ENABLED` with value `false` for now. This prevents off-season hourly polling and protects the Owls request budget. Change it to `true` when NCAAB game markets begin posting for the season.

Manual workflow runs are always allowed, even while this variable is `false`.

## 4. Smoke test the archive

GitHub -> Actions -> **CBB Owls Best Odds Archive** -> Run workflow -> `hourly`.

A successful run should insert `spread` and `moneyline` rows for currently available pregame NCAAB events. The dashboard will read those rows automatically when a published model board matches an archived event.

## Schedule

- `:17` every hour: full NCAAB best-odds archive snapshot while `CBB_ODDS_ARCHIVE_ENABLED=true`.
- The first stored quote becomes the tracked `open`; every subsequent hourly quote remains in history.
- If an hourly capture occurs within 25 minutes of tip, that same real observation is also marked as the tracked `close`. Otherwise, the first post-tip hourly run preserves the final actually stored pregame snapshot as `close` with trigger `finalize_last_pregame`. No price is fabricated.

## Important definition

`close` is our **tracked closing snapshot**, not a claim that it is the sportsbook's final tick to the second. GitHub Actions can be delayed and sportsbook feeds update asynchronously. The stored timestamp and capture trigger preserve that distinction.

## Before the season

GitHub may disable scheduled workflows in inactive public repositories after long periods without repository activity. Check that **CBB Owls Best Odds Archive** is enabled in the Actions tab before opening week.
