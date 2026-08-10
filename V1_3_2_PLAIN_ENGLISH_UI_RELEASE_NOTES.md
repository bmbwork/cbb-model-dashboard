# CBB Dashboard v1.3.2 — Plain-English UI

## Goal
Reduce bettor-facing jargon without removing analytical depth. The underlying model fields and calculations are unchanged.

## Main changes
- Replaced P10/P90 terminology with a plain-English **Likely result range** such as “Lose by 4 to win by 12.”
- Replaced AdjO / AdjD / AdjNet with **Offense rating / Defense rating / Overall rating**.
- Replaced D-I SOS / SOS gap with **Schedule strength** and plain-English schedule comparisons.
- Replaced Margin SD with **Typical margin swing**.
- Replaced Data Quality with **Data confidence**.
- Replaced Expected Pace with **Projected game speed**.
- Replaced model fair ML with **Model-implied odds**.
- Rewrote model reasons and risks in normal language.
- Added hover definitions to metric cards and a collapsible metric glossary inside each game dossier.
- Simplified the Performance Lab headline metrics and moved Brier/log loss into an explained Advanced probability checks section.
- Renamed public table columns so raw model field abbreviations are not exposed.

## Model firewall
No prediction logic, probability, score, spread, ranking, calibration, grading, market storage, or Supabase schema is changed by this patch. It is presentation-only.
