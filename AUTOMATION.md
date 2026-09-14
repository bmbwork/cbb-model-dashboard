# CBB Production Automation

This repository owns the website/publishing automation around the frozen **CBB V1.1.3B** champion. The private champion itself is not committed here.

## Forecast cadence

`com.statfactory.cbb-model-refresh` is a lightweight macOS `launchd` dispatcher that polls every 30 minutes.

For each Chicago game date it maintains three immutable forecast stages:

- **EARLY** — 18:15 CT on the prior evening for the next day's slate.
- **MID** — first tip minus 10 hours, but never earlier than 06:15 CT. If no published board exists yet, 08:15 CT is the fallback and is only eligible through 10:00 CT.
- **LATE** — first tip minus 3 hours and never after first tip.

If the Mac sleeps through EARLY, the next scheduled poll after wake catches that stage up only while it is still earlier than the MID window. Once MID is due, EARLY is superseded rather than backfilled. Once LATE is due, any unfinished EARLY/MID stage is superseded. Completed stages never duplicate.

The dispatcher state file is:

`~/.config/stat_factory/cbb_dispatch_state.json`

## Background-safe runtime isolation

Production `launchd` jobs do not execute Python, dashboard code, or the private champion from Desktop/iCloud File Provider paths.

Managed locations:

- automation Python: `~/Library/Application Support/StatFactory/CBB/venv/bin/python`
- dashboard runtime: `~/Library/Application Support/StatFactory/CBB/dashboard_runtime`
- private champion runtime: `~/Library/Application Support/StatFactory/CBB/champion_runtime`
- protected config: `~/.config/stat_factory/cbb_automation.json`
- protected publishing env: `~/.config/stat_factory/cbb_automation.env`

The model-refresh installer stages the current dashboard automation code and the private frozen champion into Application Support. It rebuilds the champion's Python 3.12 virtual environment from the champion's own `requirements.txt`, verifies the staged V1.1.3B source files byte-for-byte by SHA-256, and then validates the automation layer before installing the LaunchAgent.

Installing or reloading either CBB LaunchAgent does **not** execute a forecast, grade a game, or write results. The installers perform dry-run validation only; normal work begins on the next 30-minute `StartInterval` poll.

The original Git checkout and private champion source can remain on Desktop for manual development/inspection. After installation they are source copies only; the background jobs point at the managed Application Support copies.

Install or repair:

```bash
bash scripts/install_cbb_model_refresh_launchd.sh "/path/to/private/CBB champion"
```

If the installer has already recorded the source path, the argument can be omitted on later repairs.

Uninstall only the forecast LaunchAgent:

```bash
bash scripts/install_cbb_model_refresh_launchd.sh --uninstall
```

## Progressive grading

`com.statfactory.cbb-auto-grade` is separate from forecasting. It polls finals and grades only verified completed games. Run its installer after the model-refresh installer has migrated the shared managed runtime:

```bash
bash scripts/install_cbb_auto_grade_launchd.sh
```

The auto-grader refreshes the managed dashboard code and points its LaunchAgent at the same Application Support runtime. It does not switch back to the source Git checkout.

GitHub's `progressive_grading.yml` remains the cloud grading path. Forecasting stays local because the private frozen champion is not stored in the public dashboard repository.

## Market collection

`.github/workflows/cbb_owls_best_odds_archive.yml` handles sportsbook collection. It automatically arms when an upcoming published CBB board exists and otherwise exits cleanly in offseason/no-slate conditions.

Sportsbook prices, line movement, ticket percentages, money percentages, CLV and editorial selections remain downstream display/decision intelligence. They never enter the V1.1.3B model.

## Logs

Forecast dispatcher:

- `~/Library/Logs/StatFactory/CBB/forecast_dispatch.log`
- `~/Library/Logs/StatFactory/CBB/forecast_dispatch_error.log`

Automatic grader:

- `~/Library/Logs/StatFactory/CBB/auto_grader.log`
- `~/Library/Logs/StatFactory/CBB/auto_grader_error.log`

Latest model refresh summary:

- `~/Library/Logs/StatFactory/CBB/last_refresh.json`

## Dry-run checks

These validate configuration without running the model or writing to Supabase:

```bash
STAT_FACTORY_HEADLESS_AUTOMATION=1 \
  "$HOME/Library/Application Support/StatFactory/CBB/venv/bin/python" \
  "$HOME/Library/Application Support/StatFactory/CBB/dashboard_runtime/scripts/dispatch_cbb_model_refresh.py" \
  --dry-run
```

```bash
STAT_FACTORY_HEADLESS_AUTOMATION=1 \
  "$HOME/Library/Application Support/StatFactory/CBB/venv/bin/python" \
  "$HOME/Library/Application Support/StatFactory/CBB/dashboard_runtime/scripts/run_cbb_auto_grade.py" \
  --dry-run
```
