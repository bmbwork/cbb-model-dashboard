from pathlib import Path


def test_requirements_include_authlib():
    req = Path('requirements.txt').read_text().lower()
    assert 'authlib>=' in req


def test_odds_api_secrets_are_top_level_in_template():
    text = Path('STREAMLIT_SECRETS_TEMPLATE.toml').read_text()
    lines = text.splitlines()
    auth_pos = next(i for i, line in enumerate(lines) if line.strip() == '[auth]')
    odds_pos = next(i for i, line in enumerate(lines) if line.startswith('THE_ODDS_API_KEY'))
    assert odds_pos < auth_pos
