# V1.4.6 — Owls Insight Historical Split Backfill

## Added

- Explicit **Historical Owls Insight backfill (MVP)** control in Admin Studio.
- A completed published slate can be selected by date and backfilled independently of the main Market Data slate selector.
- The historical request uses `/api/v1/history/public-betting` with `sport=ncaab`, `startDate=<slate>`, `endDate=<slate>`, `limit=100`, and pagination.
- Saturday-sized NCAAB archives are paginated beyond the first 100 provider records.
- Owner can choose whether a historical backfill also refreshes the public non-numeric betting/sharp-money commentary.
- Backfill results show provider record count, archive pages fetched, game-mapping coverage, owner-only split rows, and sharp-money coverage.
- Historical records with no provider timestamp receive a deterministic end-of-day archive timestamp so rerunning the same backfill does not create timestamp-driven duplicate hashes.

## 2026-02-07 workflow

1. Make sure the `2026-02-07` decision board is already published in the website database.
2. Open **Admin Studio → Market Data → Historical Owls Insight backfill (MVP)**.
3. Select `2026-02-07`.
4. Leave **Update public plain-English crowd/sharp commentary** checked if the public cards should receive the derived qualitative read.
5. Click **Backfill historical Owls betting splits**.

## Storage / model integrity

- No new Supabase migration is required. V1.4.6 reuses the owner-only split table created by the v1.4.5 migration.
- Raw Owls percentages remain owner-only.
- Historical splits never become sportsbook decision or closing lines.
- V1.1.3B remains market-blind.
