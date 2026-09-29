from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_environmental_backdrop_is_local_original_and_responsive():
    theme = (ROOT / "cbb_dashboard/ui.py").read_text()
    assert "GLOBAL_CSS += BACKGROUND_ART_CSS" in theme
    assert "arena illustration" in theme
    assert "data:image/svg+xml" in theme
    assert "background-attachment:fixed" in theme
    assert "prefers-reduced-motion:reduce" in theme
    assert "auto 100vh" in theme
    assert "url(\"http" not in theme


def test_visible_player_focus_and_glass_card_contract():
    theme = (ROOT / "cbb_dashboard/ui.py").read_text()
    assert "PLAYER_FOCUS_CSS" in theme
    assert 'data:image/svg+xml' in theme
    assert 'position:fixed' in theme
    assert 'right:1.5vw' in theme
    assert 'rgba(30,13,16,.62)' in theme
    assert 'backdrop-filter:blur(12px)' in theme
    assert 'opacity:1!important' in theme
