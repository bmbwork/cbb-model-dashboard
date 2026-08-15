from pathlib import Path


def test_requirements_include_authlib():
    req = Path('requirements.txt').read_text().lower()
    assert 'authlib>=' in req




def test_owls_secret_is_top_level_in_template():
    text = Path("STREAMLIT_SECRETS_TEMPLATE.toml").read_text()
    lines = text.splitlines()
    auth_pos = next(i for i, line in enumerate(lines) if line.strip() == "[auth]")
    owls_pos = next(i for i, line in enumerate(lines) if line.startswith("OWLS_INSIGHT_API_KEY"))
    assert owls_pos < auth_pos
    assert "THE_ODDS_API_KEY" not in text
