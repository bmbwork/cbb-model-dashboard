# Validation Report — CBB Dashboard v1.4.2

## Scope

Validated the switch to The Odds API as the primary automated sportsbook-line provider while preserving the downstream market firewall, existing Supabase market contract, historical compatibility, ATS/CLV provenance and public read-only controls.

## Automated tests

- 69/69 pytest tests passed.
- Python compilation passed for `app.py` and all `cbb_dashboard/*.py` modules.
- Shell syntax validation passed for `upgrade_github_v1_4_2.sh`.

## Provider checks

- NCAA men's basketball sport key is `basketball_ncaab`.
- Featured markets requested: moneyline (`h2h`), spreads and totals.
- Region configuration defaults to `us` and can be replaced by an explicit bookmaker list.
- Reference sportsbook defaults to DraftKings and falls back only to another named returned sportsbook when necessary.
- Reference-book spread/price is kept separate from cross-book disagreement diagnostics.
- Cross-book spread min/max/range and agreement labels are calculated without changing the model.
- Ticket % and money % remain null for The Odds API; no split values are inferred or fabricated.
- Provider quota response headers are captured for admin cost monitoring.
- Historical endpoint support is explicit and user-triggered only.

## Market-integrity checks

- V1.1.3B pick, win probability, fair spread and projected score are unchanged after market attachment.
- Decision-time/taken sportsbook spread remains the only market line eligible for ATS grading.
- Closing spread remains separate for CLV/reference.
- Post-start snapshots cannot replace the pregame displayed/graded state.
- First tracked spread is used as the tracked opening only when no explicit opener exists.
- Public betting-split UI remains blank/clearly labeled when no authorized split source is present.

## Security/storage checks

- No API key is committed in the package.
- The key is read from Streamlit Secrets only.
- Supabase market tables remain public SELECT / server-write only under RLS.
- Migration is additive/idempotent and does not rewrite `cbb_slates`.

## External boundary

A live The Odds API round trip was not executed because no user credential is available in the build environment. The adapter was validated against the provider's documented response shape and synthetic multi-book NCAA basketball payloads. Live credential validation should be performed after deployment using Admin Studio.

## Deployment smoke test

A temporary Git remote/repository was initialized from the prior v1.4.1 package. `upgrade_github_v1_4_2.sh` successfully:

1. pulled `main`;
2. copied the v1.4.2 files;
3. compiled Python;
4. ran all 69 tests;
5. committed the upgrade; and
6. pushed the new commit to the mock `origin/main`.

This validates the same one-command upgrade path used by the production repository.
