from pathlib import Path

def test_archive_preserves_values_and_restricts_writes():
    sql=(Path(__file__).resolve().parents[1]/'supabase/automation_revision_archive.sql').read_text()
    assert 'primary key(slate_date, revision)' in sql
    assert 'enable row level security' in sql
    assert "Immutable forecast revision cannot be overwritten" in sql
    assert 'security invoker' in sql
    assert 'from public, anon, authenticated' in sql

def test_grade_update_uses_optimistic_forecast_hash_guard():
    root=Path(__file__).resolve().parents[1]
    source=(root/'cbb_dashboard/storage.py').read_text()
    assert '.eq("board_sha256", existing["board_sha256"])' in source
