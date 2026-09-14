from __future__ import annotations

import pandas as pd

from cbb_dashboard import premium_ui_patch


def _reset_logo_state():
    premium_ui_patch._LOGO_CACHE.clear()
    premium_ui_patch._DIRECTORY.clear()
    premium_ui_patch._SCOREBOARD_DIRECTORIES.clear()
    premium_ui_patch._SCOREBOARD_ATTEMPTED_AT.clear()


def test_scoreboard_logo_lookup_uses_actual_slate_date(monkeypatch):
    _reset_logo_state()
    seen = []

    def fake_fetch(url: str) -> dict:
        seen.append(url)
        if "scoreboard" in url:
            return {
                "events": [{
                    "competitions": [{
                        "competitors": [
                            {"team": {"id": "139", "displayName": "La Salle Explorers", "shortDisplayName": "La Salle", "abbreviation": "LAS", "logo": "https://example.test/lasalle.png"}},
                            {"team": {"id": "1390", "displayName": "Saint Louis Billikens", "shortDisplayName": "Saint Louis", "abbreviation": "SLU", "logo": "https://example.test/slu.png"}},
                        ]
                    }]
                }]
            }
        return {}

    monkeypatch.setattr(premium_ui_patch, "_fetch_json", fake_fetch)
    monkeypatch.setattr(premium_ui_patch, "_team_directory", lambda: {})
    assert premium_ui_patch.team_logo_url("La Salle", "20260207") == "https://example.test/lasalle.png"
    assert any("dates=20260207" in url for url in seen)


def test_matchup_banner_passes_target_date_to_logo_resolver(monkeypatch):
    captured = []

    def fake_logo(team: str, game_date: str = "") -> str:
        captured.append((team, game_date))
        return f"https://example.test/{team.replace(' ', '-').lower()}.png"

    monkeypatch.setattr(premium_ui_patch, "team_logo_url", fake_logo)
    row = pd.Series({"Away Team": "La Salle", "Home Team": "Saint Louis", "Target Date": "2026-02-07"})
    html = premium_ui_patch._matchup_banner(row)
    assert ("La Salle", "20260207") in captured
    assert ("Saint Louis", "20260207") in captured
    assert "cbb-logo-fallback" not in html
    assert "<img" in html


def test_validated_spread_money_and_ticket_splits_render():
    row = pd.Series({
        "Away Team": "Duke",
        "Home Team": "North Carolina",
        "_market_current_away_spread": 2.5,
        "_market_current_home_spread": -2.5,
        "_market_away_money_pct": 38.0,
        "_market_home_money_pct": 62.0,
        "_market_away_ticket_pct": 45.0,
        "_market_home_ticket_pct": 55.0,
        "_market_split_source_label": "Owls Insight",
    })
    html = premium_ui_patch.premium_betting_splits_html(row)
    assert "SPREAD MONEY" in html
    assert "Duke +2.5" in html
    assert "North Carolina -2.5" in html
    assert "38%" in html and "62%" in html
    assert "Tickets: Duke +2.5 45%" in html
    assert "OWLS INSIGHT" in html


def test_malformed_or_all_zero_money_split_stays_hidden():
    malformed = premium_ui_patch._money_card("SPREAD MONEY", "Away", 70, 55, "Home", 20, 45)
    zeroes = premium_ui_patch._money_card("SPREAD MONEY", "Away", 0, 0, "Home", 0, 0)
    assert malformed == ""
    assert zeroes == ""
