# CBB Model Dashboard v1.3 — Betting Intelligence

Streamlit presentation layer for the CBB V1.1.3B production champion. Public users remain read-only. The website displays published pregame forecasts, optional downstream market context, and official grading; it never reruns, retrains, rescales, or alters the independent prediction engine.

## v1.3 highlights

- Bettor-first game cards: model side, win probability, model line, model fair ML, projected score/total, pace, uncertainty band and data quality.
- Removes old challenger/baseline/calibration plumbing from bettor-facing cards and the public decision table.
- Rich **Game Intelligence Dossiers** with:
  - why the model likes the pick;
  - what can beat the pick;
  - two full team profile cards;
  - adjusted offense, defense, net efficiency and D-I SOS;
  - optional true pregame PPG / PPG allowed;
  - matchup battlegrounds;
  - availability, uncertainty and data quality;
  - optional downstream market context.
- Expanded **Team Intelligence** page with a team dossier hero, current matchup profile, opponent profile and matchup battleground.
- Upgraded result treatment: green W banner for a winning ML or ATS grade and a stronger gold W sweep banner when both hit.
- Correct betting-line accounting:
  - ATS grades against a stored decision-time/taken spread or explicit grader result;
  - closing spread is stored separately for CLV reference;
  - closing spread is never substituted as the ATS bet line;
  - model fair spread is never treated as a sportsbook line.
- Market/model gap is display-only and never creates an automatic BET, LEAN, PASS or +EV label.
- Performance Laboratory now presents a production evidence view rather than public challenger comparisons.
- Historical 1.1.x published slates remain backward-compatible.

## PPG / PPG allowed

The UI supports these fields when the production board exports them. If true pregame PPG / PPG allowed are absent, the site displays `—`. It never back-solves them from projected scores or adjusted efficiency.

## Database

No Supabase migration is required for v1.3. Existing `cbb_slates` JSON storage, authentication and RLS remain compatible. Optional decision/closing market fields can travel inside the existing published JSON payload.

## Deploy

From the v1.3 patch folder:

```bash
bash upgrade_github_v1_3.sh
```

The script targets `~/Desktop/cbb-model-dashboard`, requires that folder to already be a Git repository, pulls `main`, installs the patch, compiles Python, runs pytest when available, commits and pushes to GitHub. Streamlit Community Cloud should redeploy automatically.
