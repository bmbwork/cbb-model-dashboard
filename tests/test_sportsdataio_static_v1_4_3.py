from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_owls_secret_is_top_level_before_auth():
    text = (ROOT / "STREAMLIT_SECRETS_TEMPLATE.toml").read_text()
    assert "OWLS_INSIGHT_API_KEY" in text
    assert text.index("OWLS_INSIGHT_API_KEY") < text.index("[auth]")
    assert "SPORTSDATAIO_API_KEY" not in text


def test_admin_exposes_owls_refresh_and_owner_guard():
    app = (ROOT / "app.py").read_text()
    assert "Capture live Owls betting splits now" in app
    assert "check_owner_splits_access" in app
    assert "publish_owner_split_records" in app
    assert "derive_public_betting_notes" in app


def test_release_keeps_the_odds_api_as_line_provider():
    app = (ROOT / "app.py").read_text()
    assert "Refresh The Odds API market lines" in app
    assert "Owls Insight live splits" in app
    assert "SPORTSBOOK LINE" not in app or "SPORTSBOOK LINE" in (ROOT / "cbb_dashboard" / "intelligence.py").read_text()
