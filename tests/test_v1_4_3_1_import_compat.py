from pathlib import Path
import ast


def test_intelligence_exports_market_interpretation_text():
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / 'cbb_dashboard' / 'intelligence.py').read_text())
    funcs = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert 'market_interpretation_text' in funcs


def test_app_has_import_compatibility_guard():
    root = Path(__file__).resolve().parents[1]
    text = (root / 'app.py').read_text()
    assert 'try:\n    from cbb_dashboard.intelligence import market_interpretation_text' in text
    assert 'except ImportError:' in text
    assert 'APP_VERSION = "1.5.0"' in text
