from __future__ import annotations

import pandas as pd

from cbb_dashboard import board_filters, premium_ui_patch
from cbb_dashboard.conference_context import (
    CONFERENCE_GAMES,
    NON_CONFERENCE_GAMES,
    attach_conference_context,
    filter_conference_status,
    parse_conference_directory,
)


def _team(name: str, abbr: str) -> dict:
    return {"displayName": name, "location": name, "abbreviation": abbr}


def test_conference_directory_and_filters_are_fail_closed():
    payload = {
        "children": [
            {"name": "Big Ten Conference", "standings": {"entries": [{"team": _team("Michigan", "MICH")}, {"team": _team("Purdue", "PUR")}]}},
            {"name": "Southeastern Conference", "standings": {"entries": [{"team": _team("Kentucky", "UK")}, {"team": _team("Alabama", "ALA")}]}},
        ]
    }
    directory = parse_conference_directory(payload)
    board = pd.DataFrame(
        [
            {"Away Team": "Michigan", "Home Team": "Purdue"},
            {"Away Team": "Kentucky", "Home Team": "Purdue"},
            {"Away Team": "Unknown College", "Home Team": "Purdue"},
        ]
    )
    enriched = attach_conference_context(board, directory=directory)
    conference = filter_conference_status(enriched, CONFERENCE_GAMES)
    nonconference = filter_conference_status(enriched, NON_CONFERENCE_GAMES)
    assert list(conference["Away Team"]) == ["Michigan"]
    assert list(nonconference["Away Team"]) == ["Kentucky"]
    assert "Unknown College" not in set(conference["Away Team"]) | set(nonconference["Away Team"])


def test_existing_context_has_priority_over_directory_lookup():
    board = pd.DataFrame([
        {
            "Away Team": "Custom Away",
            "Home Team": "Custom Home",
            "Away Conference": "League X",
            "Home Conference": "League X",
        }
    ])
    enriched = attach_conference_context(board, directory={})
    assert bool(enriched.iloc[0]["Conference Game"]) is True
    assert enriched.iloc[0]["Away Conference"] == "League X"


def test_money_bar_uses_overlay_labels_for_extreme_splits():
    html = premium_ui_patch._money_card("SPREAD MONEY", "Away +7.0", 9, 35, "Home -7.0", 91, 65)
    assert "cbb-money-meter" in html
    assert 'style="width:9.0%"' in html
    assert 'style="width:91.0%"' in html
    assert '<span class="cbb-money-pct left">9%</span>' in html
    assert '<span class="cbb-money-pct right">91%</span>' in html
    assert '>9%</span><span class="right"' not in html


def test_logo_resolver_retries_transient_failure(monkeypatch):
    premium_ui_patch._LOGO_CACHE.clear()
    premium_ui_patch._DIRECTORY.clear()
    monkeypatch.setattr(premium_ui_patch, "_team_directory", lambda: {})
    calls = {"n": 0}

    def fake_fetch(url: str) -> dict:
        calls["n"] += 1
        if calls["n"] == 1:
            return {}
        return {"team": {"displayName": "Duke Blue Devils", "logos": [{"href": "https://example.test/duke.png"}]}}

    monkeypatch.setattr(premium_ui_patch, "_fetch_json", fake_fetch)
    assert premium_ui_patch.team_logo_url("Duke") == ""
    assert premium_ui_patch.team_logo_url("Duke") == "https://example.test/duke.png"


def test_package_installs_conference_filter_wrapper():
    assert getattr(board_filters.filter_board, "_sf_conference_filter", False)
