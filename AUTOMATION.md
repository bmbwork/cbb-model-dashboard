# CBB Production Automation

This repository owns the website/publishing automation around the frozen **CBB V1.1.3B** champion. The private champion itself is not committed here.

## Forecast cadence

`com.statfactory.cbb-model-refresh` is a lightweight macOS `launchd` dispatcher that wakes every 30 minutes and once at login.

For each Chicago game date it maintains three immutable forecast stages:

- **EARLY** — 18:15 CT on the prior evening for the next day's slate.
- **MID** — first tip minus 10 hours, but never earlier than 06:15 CT. If no published board exists yet, 08:15 CT is the fallback and is only eligible through 10:00 CT.
- **LATE** — first tip minus 3 hours and never after first tip.

If the Mac sleeps through EARLY, the dispatcher catches that stage up after wake only while it is still earlier than the MID window. Once MID is due, EARLY is superseded rather than backfilled. Once LATE is due, any unfinished EARLY/MID stage is superseded. Completed stages never duplicate.

The dispatcher state file is:

`~/.config/stat_factory/cbb_dispatch_state.json`

## Runtime isolation

The launchd interpreter is intentionally kept outside Desktop/iCloud/File Provider paths:

`~/Library/Application Support/StatFactory/CBB/venv/bin/python`

The installer builds that managed Python 3.12 environment from `requirements-automation.lock`, validates imports, validates the frozen champion/configuration, and then installs the LaunchAgent.

Install or repair:

```bash
bash scripts/install_cbb_model_refresh_launchd.sh "/path/to/private/CBB champion"
```

Uninstall only the forecast LaunchAgent:

```bash
bash scripts/install_cbb_model_refresh_launchd.sh --uninstall
```

## Progressive grading

`com.statfactory.cbb-auto-grade` is separate from forecasting. It polls finals and grades only verified completed games. Its launcher also uses the managed App Support runtime rather than the repository `.venv`.

GitHub's `progressive_grading.yml` remains the cloud grading path. Forecasting stays local because the private frozen champion is not stored in the public dashboard repository.

## Market collection

`.github/workflows/cbb_owls_best_odds_archive.yml` handles sportsbook collection. It automatically arms when an upcoming published CBB board exists and otherwise exits cleanly in offseason/no-slate conditions.

Sportsbook prices, line movement, ticket percentages, money percentages, CLV and editorial selections remain downstream display/decision intelligence. They never enter the V1.1.3B model.

## Logs

Forecast dispatcher:

- `~/Library/Logs/StatFactory/CBB/forecast_dispatch.log`
- `~/Library/Logs/StatFactory/CBB/forecast_dispatch_error.log`

Latest model refresh summary:

- `~/Library/Logs/StatFactory/CBB/last_refresh.json`

## Dry-run checks

These validate configuration without running the model or writing to Supabase:

```bash
STAT_FACTORY_HEADLESS_AUTOMATION=1 \
  "$HOME/Library/Application Support/StatFactory/CBB/venv/bin/python" \
  scripts/dispatch_cbb_model_refresh.py --dry-run
```

```bash
STAT_FACTORY_HEADLESS_AUTOMATION=1 \
  "$HOME/Library/Application Support/StatFactory/CBB/venv/bin/python" \
  scripts/run_cbb_auto_grade.py --dry-run
```
