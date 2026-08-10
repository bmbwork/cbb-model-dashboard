# CBB Dashboard v1.2 — Champion Terminal Release Notes

## Production UI

The dashboard now treats V1.1.3B as the production champion. Frozen V1.0.1 remains visible only as an audit anchor. Historical 1.1.x slates remain readable.

## Raw source-code rendering fix

Generated game-card markup is now dedented and compacted to a single logical HTML line before it reaches `st.markdown(..., unsafe_allow_html=True)`. This removes Markdown's four-space code-block interpretation that could render the second and later card as visible HTML source.

A regression test requires multi-card output to contain no newlines and to render the expected number of game-card containers.

## Graded result ribbons

- **ML W**: green when `Model Winner Correct` is true.
- **SPREAD W**: gold when the grading payload contains either an explicit ATS/spread result or a real sportsbook home spread.
- Losses are muted red.
- If no sportsbook line is stored, the card says `SPREAD —` rather than manufacturing a result.

Supported sportsbook home-line field names are currently:
- `Closing Home Spread`
- `Market Home Spread`
- `Sportsbook Home Spread`
- `Bet Home Spread`

For a standard home-line convention, ATS is graded with `Actual Home Margin + Home Spread`. Pushes are left ungraded.

## Game Intelligence Dossier

Every game card now contains an expandable dossier with:
- Why we like the model pick
- Risks / reasons for caution
- Pick vs opponent AdjO, AdjD, AdjNet and D-I SOS
- Optional true pregame PPG and PPG allowed
- Matchup and availability adjustments
- Pace, P10/P90 margin interval, data quality
- V1.0.1 anchor margin vs B calibrated margin and B adjustment

PPG fields are shown only if they exist in the published board. The website never substitutes projected score or adjusted efficiency and calls it PPG.

## Scientific separation

The website remains observational. Sportsbook lines may be stored downstream for grading/decision support but do not enter V1.1.3B. Champion performance is separated from archived challenger history by default.
