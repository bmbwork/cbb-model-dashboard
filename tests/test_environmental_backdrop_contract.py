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
