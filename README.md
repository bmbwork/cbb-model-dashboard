# CBB Model Dashboard v1.2 — Champion Terminal

Streamlit presentation layer for the CBB V1.1.3B production champion. The website remains downstream and read-only for public users: it displays published model output and official grading but never reruns or alters the prediction engine.

## v1.2 highlights

- Fixes the multi-card raw-HTML rendering defect by compacting generated card markup before Streamlit Markdown rendering.
- Rebrands the main surface around **V1.1.3B Production Champion** while preserving old 1.1.x archive compatibility.
- Adds expandable **Game Intelligence Dossiers** with “Why we like the pick”, “Risks / reasons for caution”, and side-by-side team profiles.
- Adds quick matchup fields for AdjO, AdjD, AdjNet, D-I SOS, matchup adjustments, availability, uncertainty, and optional true pregame PPG / PPG allowed.
- Adds graded result ribbons: green **ML W** and gold **SPREAD W**.
- ATS/spread grading is deliberately shown only when an explicit spread result or a stored sportsbook home spread exists. The model's own fair spread is never treated as the sportsbook line.
- Performance Lab defaults to V1.1.3B-only evidence once champion grading exists, keeping archived challenger results separate.

## No database migration required

v1.2 continues to use the existing `cbb_slates` board/grading JSON storage. Existing Streamlit secrets and Supabase RLS configuration remain valid.

## Deploy

Use the included `upgrade_github_v1_2.sh` from the patch package, or replace the repository files and push `main` normally. Streamlit Community Cloud will redeploy from GitHub.
