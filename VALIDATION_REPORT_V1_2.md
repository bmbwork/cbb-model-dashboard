# CBB Dashboard v1.2 — Validation Report

## Automated validation

- Python compilation: PASS
- Existing v1.1 tests plus v1.2 regression tests: 21 passed
- Multi-card raw-HTML regression: PASS (generated card grid contains no newline/code-indentation path)
- Exact V1.1.3B output compatibility smoke test: PASS using the current champion builder against historical pregame-schema rows
- Graded ML-W rendering: PASS
- Stored-market-spread ATS-W derivation/rendering: PASS
- Guardrail preventing `Fair Spread` from being silently treated as a sportsbook line: PASS
- Existing uploader isolation / RLS static security tests: PASS

## Architecture boundary

No Supabase migration is required. No credentials are included. The website remains downstream of the CBB model and cannot modify predictions.

## Live boundary

A deployed Streamlit/Supabase/OIDC smoke test still must be performed after GitHub push because live credentials and the hosted runtime are intentionally unavailable in the build environment.
