from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sportsdataio_secret_is_top_level_before_auth():
    text = (ROOT / "STREAMLIT_SECRETS_TEMPLATE.toml").read_text()
    assert "SPORTSDATAIO_API_KEY" in text
    assert text.index("SPORTSDATAIO_API_KEY") < text.index("\n[auth]\n")
    assert 'SPORTSDATAIO_SPLITS_MODE = "trial"' in text


def test_admin_exposes_sportsdataio_refresh_and_trial_guard():
    app = (ROOT / "app.py").read_text()
    assert "Refresh SportsDataIO public betting splits" in app
    assert "preview-only" in app
    assert "Nothing was published publicly" in app
    assert 'APP_VERSION = "1.4.3"' in app


def test_release_does_not_replace_the_odds_api_line_provider():
    app = (ROOT / "app.py").read_text()
    assert "Refresh The Odds API market lines" in app
    assert "SportsDataIO public betting splits" in app
