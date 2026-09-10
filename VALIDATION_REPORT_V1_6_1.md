# CBB Dashboard v1.6.1 — Validation Report

## Scope

Validation covers the installed v1.6.0 UI plus the new scheduled V1.1.3B production automation.

## Source-of-truth checks

- Production GitHub `main` was re-inspected immediately before deployment and reported the installed `APP_VERSION = "1.6.0"` UI release.
- Existing GitHub workflows contained only the analyst-feed CI job and the Owls best-odds archive job; there was no scheduled champion-model workflow in the website repository.
- The frozen champion package exposes `run_cbb_champion.sh` and defaults to one target date per invocation.
- No frozen champion source/model files are included in this dashboard patch.

## Automation behavior validated

- Monday target window: Monday, Tuesday, Wednesday.
- Wednesday target window: Wednesday, Thursday, Friday.
- Saturday target window: Saturday, Sunday.
- Non-scheduled manual invocation defaults to one date.
- Scheduled batches publish future dates first and the anchor/current date last so the v1.6.0 publication-recency default remains on the current slate.
- Every scheduled target uses the existing frozen `run_cbb_champion.sh` entrypoint.
- `--refresh-data` is passed by default.
- Model return code 3 is handled as a no-games skip.
- Website-ready boards are validated before publication.
- Publication uses the existing Supabase slate store and revision semantics.
- The automation runner contains no `OWLS_INSIGHT_API_KEY` reference and does not read market-current fields.
- A lock prevents overlapping scheduled model refreshes.
- Logs and last-run state are written outside the Git repository.

## Sportsbook schedule review

The existing `.github/workflows/cbb_owls_best_odds_archive.yml` remains hourly at minute 17, gated by `CBB_ODDS_ARCHIVE_ENABLED=true`.

The archive runner already supports hourly capture and near-tip tracked close behavior. The release deliberately does not reduce sportsbook capture to two fixed daily pulls because that would degrade market-movement history and tracked-close quality.

## Tests in build container

The targeted production-automation test file passed after the final deployment adjustment:

```text
5 passed
Python compile check: PASS
```

The larger v1.6.0 UI suite was validated before its existing production commit and was not rewritten by this automation-only commit.

## Security

- Supabase server credentials are never written into the Git repository.
- Prompted local credentials are stored under `~/.config/stat_factory/` with owner-only permissions.
- No model API or sportsbook secrets are copied into the patch.
- The market-blind forecast/market-data firewall remains intact.

## Not validated in this environment

- Live CBBD API calls using the user's private model key.
- Live Supabase publication using the user's private server key.
- `launchctl bootstrap` on the user's Mac.
- A real in-season scheduled run because the current date is before the college-basketball regular season.

These are intentionally deferred to the user's Mac, where the setup script performs a dry-run configuration validation before registering the launchd job.
