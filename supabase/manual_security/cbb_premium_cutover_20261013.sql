-- Stat Factory CBB subscriber-data cutover — MANUAL / GUARDED.
-- This is NOT an automatic migration. Do not run until the Streamlit server-only
-- reader is deployed, has its child-project private credential, and a real
-- entitled launch + non-entitled launch have been verified end-to-end.
-- Direct Data API REST and GraphQL paths must both be tested after this change.
-- For an intentional same-session execution, the release operator must first
-- issue: SET stat_factory.private_readers_verified = 'on';
-- The value is a RELEASE GUARD, not a substitute for the actual evidence.
BEGIN;
DO $security$
BEGIN
 IF current_setting('stat_factory.private_readers_verified', true) IS DISTINCT FROM 'on' THEN
   RAISE EXCEPTION 'Refusing premium cutover before private readers and paid entitlements are verified';
 END IF;
END
$security$;
-- Ensure the private Streamlit/Next.js service client has direct view grants.
GRANT SELECT ON public."cbb_consensus_splits",
                public."cbb_game_context",
                public."cbb_market_snapshots",
                public."cbb_owls_best_odds_card_state",
                public."cbb_slate_revisions",
                public."cbb_slates",
                public."cbb_owls_best_odds_archive" TO service_role;
-- Child anon and child authenticated JWTs do NOT represent parent subscriptions.
REVOKE SELECT ON public."cbb_consensus_splits",
                 public."cbb_game_context",
                 public."cbb_market_snapshots",
                 public."cbb_owls_best_odds_card_state",
                 public."cbb_slate_revisions",
                 public."cbb_slates",
                 public."cbb_owls_best_odds_archive" FROM PUBLIC, anon, authenticated;
-- Defense in depth: remove permissive subscriber-data RLS policies.
DROP POLICY IF EXISTS "public can read CBB aggregated consensus splits" ON public."cbb_consensus_splits";
DROP POLICY IF EXISTS "cbb_game_context_public_read" ON public."cbb_game_context";
DROP POLICY IF EXISTS "cbb_market_snapshots_public_read" ON public."cbb_market_snapshots";
DROP POLICY IF EXISTS "CBB public reads best odds archive" ON public."cbb_owls_best_odds_archive";
DROP POLICY IF EXISTS "cbb_revisions_published_read" ON public."cbb_slate_revisions";
DROP POLICY IF EXISTS "cbb_slates_public_read" ON public."cbb_slates";
COMMIT;
-- Post-cutover: SQL impersonation for anon & authenticated must deny SELECT.
-- REST and GraphQL must also reject unauthenticated requests (no paid rows).
-- Verify the same previously published board via service_role and a live
-- entitled Streamlit launch. Never re-enable anon grants as a rollback default.
