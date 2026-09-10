# CBB Dashboard v1.6.1 — Production Automation

## Purpose

V1.6.1 is an operational automation add-on to the installed v1.6.0 Stat Factory UI release. It adds scheduled production refresh support for the frozen CBB V1.1.3B champion without changing the forecasting model.

The forecasting model is not modified.

## Scheduled champion refresh

A new local macOS `launchd` job runs the frozen production entrypoint three times per week:

- Monday 05:15 local: Monday, Tuesday, Wednesday slates.
- Wednesday 05:15 local: Wednesday, Thursday, Friday slates.
- Saturday 05:15 local: Saturday, Sunday slates.

The Wednesday slate is intentionally refreshed on Wednesday even if it was first published Monday. This gives the public board a newer model/data snapshot without mutating the frozen model.

Each target invokes:

```text
run_cbb_champion.sh --date YYYY-MM-DD --refresh-data
```

A champion return code of 3 (`NO_GAMES_FOUND`) is treated as a clean skip rather than an automation failure.

## Automatic website publication

Successful website-ready CSVs are validated by the dashboard's existing `normalize_board` contract and published through `SupabaseSlateStore.publish_board` using the existing revision rules.

The scheduler does not scrape or reuse sportsbook fields as model inputs. The model process receives no Owls credential and no sportsbook data.

Local publishing uses the Supabase server credential from:

1. environment variables, or
2. `~/.config/stat_factory/cbb_automation.env`, or
3. the local uncommitted `.streamlit/secrets.toml` file.

The setup installer stores prompted credentials only in the user configuration directory with mode 600.

## Today's Board safety for multi-date publication

The installed v1.6.0 dashboard defaults to the most recently published slate. To keep the current-day slate on Today's Board without another UI rewrite, scheduled automation publishes future dates first and the anchor/current date last. Slates by Date remains explicitly selectable by calendar date.

## Sportsbook archive

No downgrade was made to the existing Owls archive cadence.

The current v1.5.0 workflow already runs hourly at minute 17 when `CBB_ODDS_ARCHIVE_ENABLED=true`. The archive code also writes a near-tip tracked close when a game is within the configured close window and can finalize a missed close from the last stored pregame snapshot.

Reducing the archive to two fixed daily pulls would materially weaken line-movement history and make CLV less reliable. Hourly archiving therefore remains the production default.

## New files

```text
scripts/run_cbb_model_refresh.py
scripts/install_cbb_model_refresh_launchd.sh
tests/test_model_automation_v1_6_1.py
V1_6_1_PRODUCTION_AUTOMATION_RELEASE_NOTES.md
VALIDATION_REPORT_V1_6_1.md
```

## Install scheduler after repository patch

```bash
bash ~/Desktop/cbb-model-dashboard/scripts/install_cbb_model_refresh_launchd.sh
```

If exactly one frozen champion installation exists under `~/Desktop`, the installer detects it automatically. If multiple copies exist, pass the exact model root as the first argument.

## Known operational limitation

The model remains local to the Mac. `launchd` cannot execute the model while the Mac is powered off. A sleeping Mac normally resumes calendar jobs on wake, but a permanently unattended production deployment would be more reliable on a dedicated always-on runner or a future private model CI repository.
