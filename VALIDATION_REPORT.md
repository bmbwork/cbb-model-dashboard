# CBB Model Dashboard v1.1 — Validation Report

## Scope

Validated the V1.1 decision-board schema, D-I cohort tagging, challenger/baseline display logic, performance calculations, publication hashing, access-control helpers, static upload isolation, Supabase RLS schema and Python/shell syntax.

## Automated tests

```text
17 passed
```

Coverage includes:

- V1.1.0 boards validate and receive internal intelligence fields;
- V1.0.1 baseline-only boards are rejected by the V1.1 publishing interface;
- winner probabilities outside 50–100% are rejected;
- internal helper fields are removed from published JSON;
- anonymous, wrong-account, unverified-email and expired identities are denied owner authorization;
- authorized email comparison is exact and case-insensitive;
- persisted audit actor does not contain the raw email;
- challenger vs baseline winner / Brier / margin metrics calculate correctly;
- Top-K and confidence bucket performance views operate on primary evaluation games;
- game cards contain V1.1, V1.0.1 and CBB-specific score/spread content;
- board hashes are deterministic and change when prediction data changes;
- exactly two file uploader calls exist and both are inside `render_admin_studio`;
- `.streamlit/secrets.toml` is ignored by Git;
- Supabase schema enables RLS, grants public SELECT and creates no public write policy.

## Static validation

```text
python3 -m py_compile app.py cbb_dashboard/*.py    PASS
bash -n bootstrap_github.sh run_local.sh           PASS
```

## Visual validation

`DESIGN_PREVIEW.png` was rendered and reviewed. The interface uses a distinct CBB palette (burgundy/charcoal, basketball orange, teal) while retaining the HR site's dense dark-card visual grammar. Desktop game cards use a two-column grid and collapse to one column on smaller screens.

## External validation boundary

A real Streamlit server, Google OIDC round trip, GitHub push and Supabase network read/write were **not** executed in this build environment. The deployment must receive one live smoke test after your own credentials and deployed URL are configured.
