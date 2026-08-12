from __future__ import annotations

from pathlib import Path

import pandas as pd

from cbb_dashboard.market import market_records, normalize_market_import
from cbb_dashboard.owlsinsight_odds_provider import (
    DEFAULT_BOOKS,
    OwlsInsightOddsConfig,
    OwlsInsightOddsProvider,
)

ROOT = Path(__file__).resolve().parents[1]


def _board() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Target Date": "2026-11-14",
                "Game ID": "g1",
                "Away Team": "North Carolina",
                "Home Team": "Duke",
                "Start Time UTC": "2026-11-14T20:00:00Z",
            }
        ]
    )


def _book_event(book_key: str, title: str, spread: float, event_id: str) -> dict:
    return {
        "id": event_id,
        "sport_key": "basketball_ncaab",
        "commence_time": "2026-11-14T20:00:00Z",
        "home_team": "Duke Blue Devils",
        "away_team": "North Carolina Tar Heels",
        "bookmakers": [
            {
                "key": book_key,
                "title": title,
                "last_update": "2026-11-14T19:30:00Z",
                "markets": [
                    {
                        "key": "spreads",
                        "outcomes": [
                            {"name": "Duke Blue Devils", "price": -110, "point": spread},
                            {"name": "North Carolina Tar Heels", "price": -110, "point": -spread},
                        ],
                    },
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Duke Blue Devils", "price": -180},
                            {"name": "North Carolina Tar Heels", "price": 155},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": -105, "point": 151.5},
                            {"name": "Under", "price": -115, "point": 151.5},
                        ],
                    },
                ],
            }
        ],
    }


def _payload() -> dict:
    return {
        "success": True,
        "data": {
            "draftkings": [_book_event("draftkings", "DraftKings", -3.5, "dk-1")],
            "fanduel": [_book_event("fanduel", "FanDuel", -3.5, "fd-1")],
            "pinnacle": [_book_event("pinnacle", "Pinnacle", -4.5, "pin-1")],
            "circa": [_book_event("circa", "Circa", -4.0, "circa-1")],
        },
        "meta": {
            "sport": "ncaab",
            "timestamp": "2026-11-14T19:31:00Z",
            "requestedBooks": ["draftkings", "fanduel", "pinnacle", "circa"],
            "availableBooks": ["draftkings", "fanduel", "pinnacle", "circa", "betmgm"],
            "booksReturned": ["draftkings", "fanduel", "pinnacle", "circa"],
            "freshness": {"ageSeconds": 2, "stale": False},
        },
    }


def test_owls_request_uses_unified_ncaab_odds_endpoint_and_bearer_auth():
    provider = OwlsInsightOddsProvider(OwlsInsightOddsConfig(api_key="owlsinsight_secret"))
    assert provider.session.headers["Authorization"] == "Bearer owlsinsight_secret"
    seen: dict = {}

    def fake(path, params=None):
        seen["path"] = path
        seen["params"] = dict(params or {})
        return _payload()

    provider._get = fake  # type: ignore[method-assign]
    provider.current_odds()
    assert seen["path"] == "/api/v1/ncaab/odds"
    assert seen["params"]["exclude_exchanges"] == "true"
    assert seen["params"]["alternates"] == "false"
    assert "draftkings" in seen["params"]["books"]
    assert "pinnacle" in DEFAULT_BOOKS


def test_unified_response_coalesces_books_and_uses_draftkings_reference():
    provider = OwlsInsightOddsProvider(OwlsInsightOddsConfig(api_key="x", reference_bookmaker="draftkings"))
    events = provider._coalesce_events(_payload())
    assert len(events) == 1
    assert {b["key"] for b in events[0]["bookmakers"]} == {"draftkings", "fanduel", "pinnacle", "circa"}

    parsed, fallback = provider.parse_event(events[0], _board().iloc[0], snapshot_role="observed")
    assert fallback is False
    assert set(parsed["Market Type"]) == {"spread", "moneyline", "total"}
    spread = parsed[parsed["Market Type"].eq("spread")].iloc[0]
    assert spread["Provider"] == "owls_insight_odds"
    assert spread["Source Label"] == "Owls Insight · DraftKings"
    assert float(spread["Home Line"]) == -3.5
    assert int(spread["Book Count"]) == 4
    assert float(spread["Home Spread Min"]) == -4.5
    assert float(spread["Home Spread Max"]) == -3.5
    assert float(spread["Book Spread Range"]) == 1.0
    assert spread["Book Agreement"] == "mixed"
    assert "consensus_home_spread=-3.75" in spread["Provider Signals"]
    assert "sharp_home_spread=-4.25" in spread["Provider Signals"]
    assert "retail_home_spread=-3.50" in spread["Provider Signals"]


def test_refresh_maps_board_and_preserves_explicit_decision_role():
    provider = OwlsInsightOddsProvider(OwlsInsightOddsConfig(api_key="x"))
    provider.current_odds = lambda: _payload()  # type: ignore[method-assign]
    snapshots, context, health = provider.refresh(_board(), snapshot_role="decision")
    assert context.empty
    assert health["provider"] == "Owls Insight"
    assert health["mapped_games"] == 1
    assert health["books_returned"] == ["draftkings", "fanduel", "pinnacle", "circa"]
    assert snapshots["Snapshot Role"].eq("decision").all()
    records = market_records(snapshots, actor="owner@example.com")
    spread = next(r for r in records if r["market_type"] == "spread")
    assert spread["home_line"] == -3.5
    assert spread["source_label"] == "Owls Insight · DraftKings"


def test_owls_odds_do_not_fabricate_ticket_or_handle_splits():
    provider = OwlsInsightOddsProvider(OwlsInsightOddsConfig(api_key="x"))
    event = provider._coalesce_events(_payload())[0]
    parsed, _ = provider.parse_event(event, _board().iloc[0])
    normalized = normalize_market_import(parsed)
    assert normalized["Home Ticket %"].isna().all()
    assert normalized["Away Ticket %"].isna().all()
    assert normalized["Home Money %"].isna().all()
    assert normalized["Away Money %"].isna().all()


def test_reference_fallback_prefers_named_major_book_and_keeps_source_label():
    payload = _payload()
    payload["data"].pop("draftkings")
    provider = OwlsInsightOddsProvider(OwlsInsightOddsConfig(api_key="x", reference_bookmaker="draftkings"))
    event = provider._coalesce_events(payload)[0]
    parsed, fallback = provider.parse_event(event, _board().iloc[0])
    assert fallback is True
    assert parsed.iloc[0]["Source Label"] == "Owls Insight · FanDuel"


def test_swapped_provider_designation_translates_back_to_board_home():
    event = _book_event("draftkings", "DraftKings", -4.5, "swapped")
    event["home_team"], event["away_team"] = event["away_team"], event["home_team"]
    spread_market = next(m for m in event["bookmakers"][0]["markets"] if m["key"] == "spreads")
    # The outcome names continue to identify actual teams; only event home/away designation is reversed.
    provider = OwlsInsightOddsProvider(OwlsInsightOddsConfig(api_key="x"))
    mapped = provider.map_board_games(_board(), [event])
    assert len(mapped) == 1 and mapped[0]["swapped"] is True
    parsed, _ = provider.parse_event(event, _board().iloc[0], swapped=True)
    row = parsed[parsed["Market Type"].eq("spread")].iloc[0]
    assert float(row["Home Line"]) == -4.5
    assert spread_market  # keep fixture explicit


def test_v148_app_and_secrets_are_owls_only_for_production_market_data():
    app = (ROOT / "app.py").read_text()
    secrets = (ROOT / "STREAMLIT_SECRETS_TEMPLATE.toml").read_text()
    assert 'APP_VERSION = "1.4.8"' in app
    assert "Refresh Owls sportsbook lines" in app
    assert "OwlsInsightOddsProvider" in app
    assert "THE_ODDS_API_KEY" not in app
    assert "OddsApiMarketProvider" not in app
    assert "THE_ODDS_API" not in secrets
    assert 'OWLS_INSIGHT_API_KEY = "owlsinsight_YOUR_FULL_KEY"' in secrets
    assert not (ROOT / "cbb_dashboard" / "odds_api_provider.py").exists()


def test_cross_book_home_away_flip_still_coalesces_single_game():
    payload = _payload()
    flipped = payload["data"]["circa"][0]
    flipped["home_team"], flipped["away_team"] = flipped["away_team"], flipped["home_team"]
    provider = OwlsInsightOddsProvider(OwlsInsightOddsConfig(api_key="x"))
    events = provider._coalesce_events(payload)
    assert len(events) == 1
    assert {b["key"] for b in events[0]["bookmakers"]} == {"draftkings", "fanduel", "pinnacle", "circa"}
