import ast
import importlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cbb_dashboard.board_filters as filters
import cbb_dashboard.ui as ui
import stat_factory_board_order as ordering


def _run_actual_startup():
    path = Path(__file__).resolve().parents[1] / "app.py"
    startup = []
    for node in ast.parse(path.read_text()).body:
        startup.append(node)
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_game_board_runtime"
            for target in node.targets
        ):
            break
    namespace = {"__file__": str(path), "__name__": "dashboard_startup_test"}
    exec(compile(ast.Module(body=startup, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def test_warm_startup_restores_ordering_filters_css_and_conference_runtime(monkeypatch):
    monkeypatch.delattr(ordering, "sort_numeric_cards")
    monkeypatch.delattr(filters, "SORT_HELP")
    monkeypatch.setattr(ui, "GLOBAL_CSS", "stale-css")
    _run_actual_startup()
    assert callable(ordering.sort_numeric_cards)
    assert filters.SORT_HELP == ordering.SORT_HELP
    assert all(choice in filters.SORT_OPTIONS for choice in ordering.SUPERLATIVE_SORT_OPTIONS)
    assert ".game-card{background:#1e0d10!important;opacity:1!important}" in ui.GLOBAL_CSS
    assert ".cbb-logo-matchup" in ui.GLOBAL_CSS
    assert ".cbb-record-summary-grid" in ui.GLOBAL_CSS
    assert getattr(filters.filter_board, "_sf_conference_filter", False)


def test_concurrent_reruns_refresh_each_dependency_once_per_source_revision(monkeypatch):
    startup = _run_actual_startup()
    refresh = startup["_refresh_game_board_runtime"]
    original = importlib.reload
    calls = []
    def tracked(module):
        calls.append(module.__name__)
        return original(module)
    monkeypatch.setattr(ordering, "_sf_game_board_source_hash", "previous-source")
    monkeypatch.setattr(importlib, "reload", tracked)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: refresh(), range(8)))
    assert calls == ["stat_factory_board_order", "cbb_dashboard.board_filters", "cbb_dashboard.ui"]
    current = filters.filter_board
    _run_actual_startup()
    assert filters.filter_board is current
