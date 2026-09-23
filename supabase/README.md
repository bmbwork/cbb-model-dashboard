> **AUTHORITATIVE REPOSITORY CONTEXT — 2026-09-23**  
> This file documents a sub-area of `bmbwork/cbb-model-dashboard`. The repository root `README.md` is the first stop for current production ownership, infrastructure, access rules, and emergency-maintainer guidance. Current production identity: **CBB V1.1.3B**. Files under research/experiment/archive/config/model subdirectories may intentionally describe non-production or historical work; do not promote or deploy them solely because their local README sounds newer. Verify the root README, production handoff/manifest, `main`, and current workflows before editing production.

# CBB Supabase Operations

> **Authoritative maintainer note — 2026-09-23**

- Repository: `bmbwork/cbb-model-dashboard`
- Production champion: **CBB V1.1.3B**
- Supabase project ref: `mtiwegegbmheefqombrw`
- Private model bucket: `cbb`
- Product key: `cbb`

## Canonical champion object

`cbb/production/CBB_V1_1_3B_Champion.zip`

Verified SHA-256:
`9f19e60919a676e842b54093b8d000478a3c228fc8328a6a4c8354abff576452`

Do not replace this object merely because a newer dashboard/UI version exists.

## Source-controlled contracts

- `supabase/schema.sql`
- `supabase/functions/stat-factory-health/index.ts`
- `docs/PRODUCTION_HANDOFF.md`

Market lifecycle data preserves observed/open/decision/close semantics. Raw split/sharp diagnostics belong in restricted server-side storage; public cards should receive only deliberately projected fields.

## Security / secrets

Prefer modern `SUPABASE_SECRET_KEY`/secret-key usage where supported; legacy service-role JWT may remain only as a compatibility fallback.

Never expose the server key or Owl key to public code.

Do not broaden access to `cbb_owner_betting_splits` simply to make a public page query work; use a narrow server-side projection instead.

## Incident diagnosis

- Forecast issue -> verify V1.1.3B board and publication.
- Odds/CLV issue -> inspect archived market snapshots/workflows.
- Split issue -> inspect validated source pairing and private split table.
- Health auth issue -> verify modern secret-key preference and Edge Function environment.

Run advisors after schema/auth changes.
