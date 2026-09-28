from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cbb_asset_shell_contract():
    ui = (ROOT / "cbb_dashboard" / "ui.py").read_text()
    assert "ASSET_REBUILD_CSS" in ui
    assert "--sf-orange:#FF7A1A" in ui
    assert "[role=\"radiogroup\"] label:has(input:checked)" in ui
    assert "linear-gradient(180deg,#FF9B48,#F97316)" in ui


def test_cbb_board_exposes_premium_research_modes():
    app = (ROOT / "app.py").read_text()
    for label in ("Cards", "Matchup Explorer", "Public Money", "Model Insights"):
        assert label in app
    assert "market_context_html(row)" in app
    assert "evidence_html(row)" in app
    assert 'st.form("cbb_game_filters"' in app


def test_cbb_home_and_human_layers_are_separated():
    app = (ROOT / "app.py").read_text()
    for label in ("GAME BOARD", "MATCHUP INTELLIGENCE", "PUBLIC MONEY", "PERFORMANCE"):
        assert label in app
    assert "ANALYST LAYER" in app
    assert "OWNER OPERATIONS" in app
