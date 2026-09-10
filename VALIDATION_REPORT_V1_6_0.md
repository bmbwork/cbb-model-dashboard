# Validation Report — CBB Dashboard v1.6.0

Validated: 2026-09-10

## Source baseline

The supplied `cbb-model-dashboard-current.zip` was compared against current GitHub `bmbwork/cbb-model-dashboard` `main` for the principal UI files before work began. The current source matched the production repository snapshot used for this patch.

## Static/source validation

PASS:

- `app.py`, UI, intelligence, storage and new filter module compile.
- Full repository `compileall` succeeds.
- `APP_VERSION` is `1.6.0`.
- Public sidebar contract is exactly Home / Today's Board / Slates by Date / Analyst Picks / Performance Lab, plus conditional Admin Studio.
- No `THE_ODDS_API_KEY` reference exists in active source/config scan.
- Existing Owls Insight production integrations remain in place.
- No model files or model artifacts are included in this patch.

## Automated tests

Container test result with security test excluded because Streamlit is not installed in the execution container:

- 115 passed

Full repository result using a test-only minimal Streamlit import stub solely to allow the existing security module to import:

- 119 passed

The stub is not included in the release artifact and is not needed in the production repository, whose Python 3.12 virtual environment already includes Streamlit.

## New v1.6.0 regression coverage

PASS:

- model-pick ML price uses the correct home/away side;
- -350 through +500 ML display filter behavior;
- AP Top 10 / Top 25 / ranked-vs-ranked filtering;
- sportsbook availability filtering;
- model-vs-market spread-gap filtering;
- line-movement filtering;
- sorting does not mutate frozen model fields;
- polished card exposes model pick, model spread, best spread, best ML, market lifecycle and betting splits;
- 0/0 split sentinels are suppressed;
- away-side 0/0 sentinel cannot be complemented into fabricated 100/100 splits;
- public card split projection uses the server/admin client, selects no line/sharp fields and forces `observed` role;
- raw split-table SQL still revokes anon/authenticated access;
- reduced public navigation and Slates by Date routing are enforced.

## Market provenance review

PASS:

The public card split projection cannot become an opening, decision or closing market line because:

1. the projection does not select line fields;
2. each projected row is overwritten to `snapshot_role = observed` before normalization;
3. existing market line/open/decision/close rows continue to come from the established market/archive paths.

## Performance review

PASS by source inspection and routing tests:

The public board, market snapshots, game context, best-odds archive and private split projection are loaded only when the active page is Today's Board or Slates by Date. This removes unnecessary board/archive queries from Home, Analyst Picks, Performance Lab and Admin Studio rerenders.

## Visual verification limitation

The requested design was implemented directly from the supplied CBB/CFB screenshots plus the current Stat Factory product hierarchy. The browser-automation CLI referenced by the browser skill was not installed in this execution container, and the available headless Chromium process did not complete reliably, so a pixel-level local Streamlit screenshot comparison was not claimed here.

The installer therefore performs source compilation and the real repository test suite before it commits/pushes. After Streamlit Cloud redeploys, a final visual pass should verify spacing at desktop and mobile widths with live production data.

## Known behavior / expected degradation

- AP filters require AP rank fields in published game context; games without ranking context are not falsely treated as ranked.
- Numeric betting splits require the existing Supabase secret/server key. If that private server-side projection is unavailable, the split strip degrades to `Not offered` while model and sportsbook-odds cards continue to render.
- Open/close/CLV display only when the corresponding tracked market state actually exists.
- ML filter operates on the best current sportsbook moneyline for the model's straight-up pick, matching the CFB workbench pattern.

## Promotion recommendation

Approved for a v1.6.0 UI patch installation subject to the installer completing the production repository's Python 3.12 compile and full test suite successfully before commit/push.
