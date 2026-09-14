# CBB preseason operations

The frozen model remains V1.1.3B. This release changes no private model source, training data, parameters or forecasts.

## Market automation
Hourly collection is now armed by actual upcoming published CBB slates (today through 14 days ahead, America/Chicago). Historical/demo boards do not activate off-season provider calls. Once the first current board is published, the existing hourly `:17` collector starts without a separate launch flag. The obsolete opt-in `CBB_ODDS_ARCHIVE_ENABLED` is replaced by an explicit emergency pause, `CBB_MARKET_PAUSED=true`.

The readiness step reports only credential-presence booleans and slate availability, never keys. A missing provider credential fails once active games exist. Readiness success in the off-season is not proof of a successful live odds archive capture.

## Grading
The existing 15-minute final-only worker now rejects malformed game IDs, boolean/fractional scores and conflicting finals, and verifies archived result writes by reading the saved digest back. Current and historical forecast revisions remain immutable. Pending games are not losses. Eight targeted grading/readiness tests passed locally before release.

## Remaining launch boundary
The authoritative forecast package and installed scheduler live on the owner's Mac. This repository still contains the earlier Monday/Wednesday/Saturday refresh installer. It does not yet establish the requested early/middle/pregame production cadence on that machine. That requires verifying the approved runtime and its pregame feature cutoff before replacing the installed schedule. No scheduled new-season forecast is claimed by this release.

Before first games: verify CBBD and Owls credentials, publish a causal upcoming V1.1.3B slate, verify the first hourly archive capture, then confirm a final-only grading pass. Do not expose the private champion package in this public dashboard repository.
