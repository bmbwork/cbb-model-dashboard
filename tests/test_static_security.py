from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _function_bounds(tree, name):
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    return fn.lineno, fn.end_lineno


def test_uploaders_exist_only_in_admin_studio():
    source = (ROOT / "app.py").read_text()
    tree = ast.parse(source)
    lo, hi = _function_bounds(tree, "render_admin_studio")
    uploader_lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "file_uploader":
            uploader_lines.append(node.lineno)
    assert len(uploader_lines) == 4
    assert all(lo <= line <= hi for line in uploader_lines)


def test_secret_file_is_ignored():
    ignored = (ROOT / ".gitignore").read_text()
    assert ".streamlit/secrets.toml" in ignored


def test_schema_has_public_select_without_public_writes():
    sql = (ROOT / "supabase" / "schema.sql").read_text().lower()
    assert "enable row level security" in sql
    assert "grant select" in sql
    assert "create policy \"cbb_slates_public_read\"" in sql
    # No public insert/update/delete policies are defined.
    assert "for insert" not in sql
    assert "for update" not in sql
    assert "for delete" not in sql


def test_app_does_not_render_admin_email():
    source = (ROOT / "app.py").read_text()
    assert "Admin: {" not in source
    assert "st.write(access.email" not in source
