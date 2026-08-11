# CBB Dashboard v1.4.2.1 Authlib Hotfix

- Adds `Authlib>=1.3.2,<2`, required by Streamlit `st.login()` / OIDC authentication.
- Clarifies that `THE_ODDS_API_*` settings are top-level TOML secrets and must appear before `[auth]` / `[auth.google]`.
- No model, market-data, ATS, CLV, Supabase-schema, or prediction changes.
