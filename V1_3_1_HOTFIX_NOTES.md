# CBB Dashboard v1.3.1 - Recent Upload Default Hotfix

## Fix
The public board now defaults to the most recently published decision board rather than the chronologically latest slate date.

Example: if 2026-04-04 was published yesterday and 2026-03-19 is published today, 2026-03-19 opens by default.

## Ordering semantics
- Default board: newest `published_at` timestamp.
- Archive selector: newest board upload first.
- Tie-breaker: slate date, then revision.
- Publishing grading alone does not change the default board because grading updates `graded_at` / `updated_at`, not `published_at`.

No Supabase migration is required. The existing `published_at` column is already populated by Admin Studio board publishing.
