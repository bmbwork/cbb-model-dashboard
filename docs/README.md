<!-- STAT_FACTORY_NESTED_README_NOTICE_V1 -->
> **Maintainer / production-safety notice — 2026-09-23**
>
> This file documents a subdirectory or historical/research surface inside `bmbwork/cbb-model-dashboard`. The repository root `README.md` is the first source of truth for current operations. Current production champion: **CBB V1.1.3B**. A folder, experiment, package, benchmark, or older document with a newer-looking label is **not** automatically production. Verify the root README, production handoff/manifest, current `main`, and live workflow state before changing or promoting anything.
>
> Preserve the market-blind model -> immutable forecast -> downstream sportsbook/analyst boundary. Never commit secrets. If this file conflicts with the root README, treat this file as subordinate until the discrepancy is deliberately resolved.

# CBB Documentation Index

Use this directory for supporting production and historical documentation. Current operational instructions live in the repository root or are linked below.

## Current operations

- `../AUTOMATION.md` — canonical forecast/grading/market automation map, managed-runtime locations, schedules and model/market firewall.
- `../DEPLOY_STREAMLIT.md` — Streamlit deployment guidance.
- `../MARKET_DATA_SETUP.md` — market-data setup and configuration.
- `../SECURITY_AND_PUBLISHING_SETUP.md` — publishing/authentication setup.
- `../ARCHIVE_SETUP_V1_5_0.md` — immutable archive setup reference.

## Historical readiness/audits

These are retained for traceability but should not be used as current operating instructions; several listed gaps were subsequently resolved:

- `archive/2026-09/AUTOMATION_AUDIT_2026_09_13.md`
- `archive/2026-09/PRESEASON_READINESS_2026_09_13.md`
- `archive/legacy/PROJECT_MANIFEST_V1_6_0.txt` — historical v1.6 file inventory; not an authoritative inventory of current main.

The private V1.1.3B champion and its credentials remain outside this public dashboard repository.
