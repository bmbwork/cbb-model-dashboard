# CBB Dashboard v1.3 — Betting Intelligence Release Notes

## Shipped

### Bettor-facing card redesign

The public game card no longer foregrounds development mechanics such as V1.0.1 comparisons, B-calibration adjustment values or old schedule-translation language. The production surface now prioritizes information a bettor can act on or interpret directly:

- model pick;
- model win probability;
- model fair spread;
- model fair moneyline;
- projected score and total;
- expected pace;
- pick-side P10/P90 margin band;
- data quality;
- availability and neutral-site context.

### Game Intelligence Dossier

Each card expands into a full matchup dossier:

- **Why the model likes the pick**
- **What can beat the pick**
- side-by-side team profiles
- AdjO / AdjD / AdjNet
- D-I SOS
- optional PPG / PPG allowed
- matchup adjustment and availability adjustment
- offense-vs-defense battleground
- uncertainty / venue / data quality
- downstream market context when a line is stored

### Team Intelligence

The Team Intelligence page now behaves like a scouting dossier rather than a duplicate table. It includes a focused team header, six key team metrics, opponent comparison, matchup battleground, model thesis/risk and market context.

### Results and ATS accounting

Result cards now use a sportsbook-style visual hierarchy:

- one winning grade -> green W treatment;
- ML + ATS sweep -> gold W treatment;
- losses remain visually subdued/red;
- ATS unavailable -> explicitly labeled, never inferred.

ATS is graded only from an explicit ATS result or a stored decision/taken spread. Closing spread is isolated for CLV reference. This prevents a closing line or the model's own fair line from being misrepresented as the line that was available/taken.

### Market firewall

Optional sportsbook spread fields are display-only. Model/market gaps and CLV can be shown when the necessary fields exist, but they do not modify the production prediction and do not generate automatic betting recommendations.

## Explicitly not shipped

- automatic BET / LEAN / PASS labels;
- unvalidated +EV claims;
- stake or bankroll ledger;
- public ticket/money split heuristics;
- market data as a production-model feature;
- synthetic PPG or PPG allowed values;
- old challenger mechanics on the public quick-scan surface.

## Compatibility

- Existing V1.1.x archived slates continue to render.
- Existing Supabase schema and Streamlit secrets remain valid.
- No database migration is required.
