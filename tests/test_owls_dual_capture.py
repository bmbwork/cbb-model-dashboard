from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd

from cbb_dashboard.market import market_records
from cbb_dashboard.owlsinsight_odds_provider import OwlsInsightOddsConfig, OwlsInsightOddsProvider
from scripts.archive_owls_best_odds import persist_published_board_market_snapshots


def board():
    return {
        "Game ID": "g1", "Away Team": "North Carolina", "Home Team": "Duke",
        "Start Time UTC": "2026-11-14T20:00:00Z", "Target Date": "2026-11-14",
        "Model Pick": "Duke", "Win Probability": 0.62,
        "Projected Away Score": 70, "Projected Home Score": 76,
        "Fair Spread": -6.0, "Fair Moneyline": -160,
        "Model Version": "1.1.3B", "Game Classification": "D1 vs D1",
        "D1 Evaluation Eligible": True, "Schedule Translation Margin Adj": 0.0,
        "V1.0.1 Baseline Pick": "Duke", "V1.0.1 Baseline Win Probability": 0.61,
        "V1.0.1 Baseline Fair Spread": -5.5,
    }


def event():
    return {
        "id": "owls-1", "home_team": "Duke Blue Devils",
        "away_team": "North Carolina Tar Heels",
        "commence_time": "2026-11-14T20:00:00Z",
        "bookmakers": [{
            "key": "draftkings", "title": "DraftKings",
            "last_update": "2026-11-14T19:30:00Z",
            "markets": [
                {"key": "spreads", "outcomes": [
                    {"name": "Duke Blue Devils", "point": -8.5, "price": -110},
                    {"name": "North Carolina Tar Heels", "point": 8.5, "price": -110},
                ]},
                {"key": "h2h", "outcomes": [
                    {"name": "Duke Blue Devils", "price": -310},
                    {"name": "North Carolina Tar Heels", "price": 250},
                ]},
                {"key": "totals", "outcomes": [
                    {"name": "Over", "point": 147.5, "price": -110},
                    {"name": "Under", "point": 147.5, "price": -110},
                ]},
            ],
        }],
    }


class FakeClient:
    def __init__(self):
        self.published = [dict(slate_date="2026-11-14", board_json=[board()])]
        self.saved = []
        self.table_name = ""

    def table(self, name):
        self.table_name = name
        return self

    def select(self, *_):
        return self

    def gte(self, *_):
        return self

    def lte(self, *_):
        return self

    def order(self, *_):
        return self

    def limit(self, *_):
        return self

    def upsert(self, items, *, on_conflict):
        assert on_conflict == "raw_snapshot_hash"
        self.saved.extend(items)
        return self

    def execute(self):
        if self.table_name == "cbb_slates":
            return SimpleNamespace(data=self.published)
        return SimpleNamespace(data=[])


def test_paired_archive_source_populates_market_snapshot_rows():
    client = FakeClient()
    provider = OwlsInsightOddsProvider(OwlsInsightOddsConfig(api_key="test"))
    result = persist_published_board_market_snapshots(
        client, provider, [event()],
        pd.Timestamp("2026-11-14T19:45:00Z"), "2026-11-14T19:30:00Z",
    )
    assert result["future_board_games"] == 1
    assert result["matched_board_games"] == 1
    assert result["snapshot_rows"] == 3
    assert result["rows_written"] == 3
    assert {r["market_type"] for r in client.saved} == {"spread", "moneyline", "total"}
    spread = next(r for r in client.saved if r["market_type"] == "spread")
    assert spread["home_line"] == -8.5
    assert spread["source_label"] == "Owls Insight · DraftKings"
    assert all(r["snapshot_role"] == "observed" for r in client.saved)
    assert all(r["opening_home_line"] is None for r in client.saved)
    assert all("sharp_side" not in r for r in client.saved)


def test_started_event_not_stored_as_pregame_quote():
    client = FakeClient()
    provider = OwlsInsightOddsProvider(OwlsInsightOddsConfig(api_key="test"))
    result = persist_published_board_market_snapshots(
        client, provider, [event()],
        pd.Timestamp("2026-11-14T20:15:00Z"), "2026-11-14T19:30:00Z",
    )
    assert result["future_board_games"] == 0
    assert result["snapshot_rows"] == 0
    assert client.saved == []


def test_generic_market_records_keep_raw_fields_for_owner_only_archives():
    from cbb_dashboard.storage import MARKET_SNAPSHOT_PRIVATE_FIELDS
    provider = OwlsInsightOddsProvider(OwlsInsightOddsConfig(api_key="test"))
    snapshot, _ = provider.parse_event(event(), pd.Series(board()))
    saved = market_records(snapshot)
    assert saved
    assert all("sharp_side" in row and "capture_trigger" in row for row in saved)
    assert {"sharp_side", "capture_trigger"}.issubset(MARKET_SNAPSHOT_PRIVATE_FIELDS)
