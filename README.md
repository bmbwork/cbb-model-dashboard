# CBB Model Dashboard v1.1 — Intelligence Terminal

A Streamlit publishing and intelligence interface for the **CBB Independent Game Engine V1.1 Schedule Translation Challenger**.

The design intentionally follows the established HR dashboard interaction model—dark surface, left navigation, ranked cards, compact metric tiles, public read-only pages and an owner-only Publishing Studio—while giving college basketball its own identity: charcoal/burgundy surfaces, basketball orange as the primary accent, teal probability highlights and score-first matchup cards.

## What is included

- **Today's Board** — ranked V1.1 matchup cards, model score projections, fair spread / fair moneyline, pace, D-I cohort markers, schedule-translation context and a full searchable board.
- **Matchup Explorer** — V1.1 vs frozen V1.0.1 comparison, team-strength chart, simulation interval, schedule-strength translation and plain-language support/risk readout.
- **Team Intelligence** — adjusted offense, defense, net efficiency, D-I SOS, matchup adjustment, availability adjustment and opponent context.
- **Performance Laboratory (early backend)** — cumulative V1.1 vs V1.0.1 walk-forward metrics once graded challenger slates are published. This is observational only.
- **Model Guide** — explains the independent engine, D-I cohort, confidence, availability and market firewall.
- **Admin Studio** — Google OIDC owner access for publishing decision-board and graded-board CSVs to Supabase.

## Security boundary

The public site is read-only. File upload widgets exist only inside the authorized Admin Studio. Supabase public access is SELECT-only through Row Level Security; database writes use the server-side secret key. The raw admin email is not stored in the published slate table; a short one-way audit identifier is used instead.

The model engine itself is not part of this repository. The website reads model outputs and never changes CBB V1.1 rankings, probabilities, spreads or scores.

## Quick local run

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

For local OIDC, use a local `.streamlit/secrets.toml` that is **not committed**. See `SECURITY_AND_PUBLISHING_SETUP.md`.

## Production deployment

See `DEPLOY_STREAMLIT.md` for GitHub + Streamlit Community Cloud deployment and `supabase/schema.sql` for the persistence layer.
