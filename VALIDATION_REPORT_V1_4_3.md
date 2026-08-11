# Validation Report — CBB Dashboard v1.4.3

Validated in the packaged source tree without production credentials.

## Automated validation

- Full pytest suite: 89 passed.
- Python compilation: PASS.
- SportsDataIO header authentication: PASS.
- API key persistence leak test: PASS.
- GameID mapping fixture: PASS.
- Spread split-history parser fixture: PASS.
- The Odds API line + SportsDataIO split merge: PASS.
- Plain-English money-vs-ticket interpretation: PASS.
- `observed` cannot become ATS decision line: PASS.
- `observed` cannot become closing line: PASS.
- Explicit decision/close separation: PASS.
- Existing historical-board/UI/security regressions: PASS.

## Live boundary

A real SportsDataIO call was not executed in the packaging environment because no user credential is copied into the build environment. Admin Studio provides trial-preview and production-publish modes for live verification after deployment.
