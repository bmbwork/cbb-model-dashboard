# CBB Website v1.1 — Intelligence Terminal Release Notes

## Shipped

- New CBB-specific Streamlit website with the established HR dashboard design language.
- Distinct burgundy / charcoal + basketball-orange + teal visual identity.
- V1.1 challenger decision-board validation and publication.
- D-I vs D-I primary-cohort treatment throughout the interface.
- Ranked score-first game cards with win probability, fair spread, fair moneyline, projected total and pace.
- Frozen V1.0.1 comparison on every matchup.
- Schedule-translation adjustment, training-sample and D-I SOS context.
- Matchup Explorer with support/risk explainability and simulation uncertainty.
- Team Intelligence profile and opponent comparison.
- Early Performance Laboratory backend for V1.1 vs V1.0.1 walk-forward grading.
- Public archive selector for historical published slates.
- Google OIDC owner authentication.
- Supabase persistence with public read-only RLS and server-only writes.
- Admin-only board and grading uploads with explicit publish confirmation.
- SHA-256 board/grading audit hashes and same-date revision controls.
- Responsive card layout for mobile devices.

## Deliberately held

- sportsbook odds;
- betting ticket or handle splits;
- line movement;
- market-aware model changes;
- +EV recommendations;
- ATS recommendations;
- market-derived confidence changes.

Those remain downstream of the independent challenger-validation phase.

## Model firewall

This GitHub repository contains the publishing/dashboard layer only. It does not contain or execute the CBB prediction engine. Published V1.1 values are displayed as immutable model outputs.
