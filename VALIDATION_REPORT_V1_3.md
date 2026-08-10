# CBB Dashboard v1.3 — Validation Report

## Scope

Validated the bettor-first card renderer, Team Intelligence dossier, historical compatibility, market/closing-line separation, ATS grading semantics, CLV display math, source-code rendering regression, public research-plumbing removal and the existing security/publishing test suite.

## Automated tests

```text
29 passed
```

Coverage includes:

- multi-card HTML stays on a single logical line and cannot fall into Markdown code-block rendering;
- production cards contain model price / total / pace / uncertainty fields;
- V1.0.1 audit and B-calibration plumbing are absent from public cards;
- team dossiers expose AdjO, AdjD, AdjNet, D-I SOS, PPG and PPG-allowed slots;
- model/market gap is calculated from the selected team's perspective;
- market comparison is explicitly display-only;
- decision/taken spread can grade ATS;
- closing spread alone cannot grade ATS;
- model fair spread cannot grade ATS;
- ML + ATS sweep renders a gold W banner;
- decision line + closing line produce correctly signed point-space CLV;
- bettor-facing board table excludes development columns;
- historical boards without champion-only columns remain safe;
- existing authentication, storage, upload isolation and RLS tests continue to pass.

## Real-board smoke tests

A real 148-row historical graded board was normalized and rendered successfully. A separate real V1.1.3 parallel graded board was re-anchored to its frozen V1.1.3B columns to mimic the production champion export surface; 20 rendered cards produced:

```text
20 cards
20 Game Intelligence Dossiers
0 HTML newlines in the generated grid
0 public V1.0.1 audit strings
0 public B-calibration strings
0 false ATS grades when no decision/taken line was supplied
```

## Static validation

```text
python3 -m py_compile app.py cbb_dashboard/*.py    PASS
```

The build environment did not contain Streamlit itself, so a live Streamlit server / Supabase / Google OIDC network round trip was not executed here. Deployment still requires the normal live smoke test after GitHub/Streamlit redeploy.
