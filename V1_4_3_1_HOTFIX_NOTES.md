# CBB Dashboard v1.4.3.1 Import Compatibility Hotfix

## Fix
Streamlit could start the new v1.4.3 `app.py` while still resolving a stale pre-v1.4.3 `cbb_dashboard.intelligence` module. The older module did not export `market_interpretation_text`, causing an ImportError at app startup.

This hotfix:
- ships the matching v1.4.3 `intelligence.py` again;
- changes `app.py` to tolerate a stale module during a rolling reload;
- clears local Python bytecode caches during installation;
- verifies that the shipped intelligence module defines `market_interpretation_text`;
- bumps the displayed application version to 1.4.3.1.

No prediction, market calculation, SportsDataIO parsing, Supabase schema, or grading logic is changed.
