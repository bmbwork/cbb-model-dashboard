# CBB Dashboard v1.3.3 — Tooltip Hotfix

## Fix
The small `?` help markers now render a visible in-app tooltip using CSS rather than relying only on the browser's native `title` behavior. Hovering the marker displays the full plain-English explanation. The same explanation is available by keyboard focus.

## No betting/model changes
This patch does not change predictions, grading, ATS logic, market-line handling, Supabase storage, or published data.

## ATS reminder
ATS grading requires a saved pregame/taken sportsbook spread. A closing spread is retained for CLV only and is not used to grade the original ATS decision.
