"""Source contract gate for the subscriber-only server-side Supabase reader.
Does not connect to production. SQL/REST must be verified separately after cutover.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_premium_reader_is_pinned_to_private_key():
    checks = [["cbb_dashboard/storage.py",["private_reader: bool = False","if private_reader:","key = str(config.secret_key or \"\").strip()"]],["app.py",["private_reader=True"]]]
    for path, required in checks:
        source = (ROOT / path).read_text(encoding="utf-8")
        for literal in required:
            assert literal in source, f"{path}: missing {literal!r}"

def test_database_cutover_is_not_applied_from_ci():
    sql = (ROOT / "supabase/manual_security/cbb_premium_cutover_20261013.sql").read_text(encoding="utf-8").lower()
    assert "current_setting('stat_factory.private_readers_verified', true)" in sql
    assert "revoke select on" in sql
    assert "grant select on" in sql
    assert "drop policy if exists" in sql
