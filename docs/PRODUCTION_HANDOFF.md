# CBB V1.1.3B Production Handoff

## Production identity

- **Production Champion:** CBB V1.1.3B
- **Repository:** `bmbwork/cbb-model-dashboard`
- **Supabase project:** `mtiwegegbmheefqombrw`
- **Private Storage bucket:** `cbb`

## Canonical champion package

```text
cbb/production/CBB_V1_1_3B_Champion.zip
```

Verified identity:

```text
size:   15580 bytes
sha256: 9f19e60919a676e842b54093b8d000478a3c228fc8328a6a4c8354abff576452
```

The package is a minimal frozen production surface extracted from the supplied champion archive. It contains the approved prediction/grade entrypoints, champion module, requirements, README, manifest and per-file SHA list. Large source datasets, caches, generated outputs, virtual environments and secrets are intentionally excluded.

The package was SHA-256 verified before upload, uploaded to private Supabase Storage, downloaded again through authenticated Storage, and SHA-256 verified a second time. The pre-upload and post-download hashes matched exactly.

## Active automation

The managed macOS V1.1.3B forecast dispatcher remains the active forecasting execution path. It is offseason-idle in September and resumes according to the documented CBB season cadence.

The presence of the canonical cloud artifact removes the previous recovery/artifact blocker but does not, by itself, change the production execution host. A future cloud runner must checksum-lock this exact object and pass the same publication/QA contract before replacing the managed scheduler.

Sportsbook/Owl information remains downstream of the market-blind champion.
