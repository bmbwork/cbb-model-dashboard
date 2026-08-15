from __future__ import annotations

from pathlib import Path

import pandas as pd

from cbb_dashboard.market import market_records, snapshots_frame
from cbb_dashboard.owlsinsight_provider import (
    OwlsInsightConfig,
    OwlsInsightSplitsProvider,
    annotate_sharp_money_signals,
)

ROOT = Path(__file__).resolve().parents[1]


def _board() -> pd.DataFrame:
    return pd.DataFrame([{
        "Target Date": "2026-08-11",
        "Game ID": "g1",
        "Away Team": "North Carolina",
        "Home Team": "Duke",
        "Model Pick": "Duke",
    }])


def _payload() -> dict:
    return {
        "sport": "ncaab",
        "data": [{
            "event_id": "owls-g1",
            "home_team": "Duke",
            "away_team": "North Carolina",
            "splits": [
                {
                    "book": "circa",
                    "title": "Circa Sports",
                    "spread": {
                        "home_line": -5.5,
                        "away_line": 5.5,
                        "home_bets_pct": 70,
                        "away_bets_pct": 30,
                        "home_handle_pct": 48,
                        "away_handle_pct": 52,
                    },
                },
                {
                    "book": "draftkings",
                    "title": "DraftKings",
                    "spread": {
                        "home_line": -6.0,
                        "away_line": 6.0,
                        "home_bets_pct": 68,
                        "away_bets_pct": 32,
                        "home_handle_pct": 45,
                        "away_handle_pct": 55,
                    },
                },
            ],
        }],
        "meta": {"source": "circa_dk"},
    }


def test_live_rows_persist_raw_splits_and_sharp_diagnostics():
    provider = OwlsInsightSplitsProvider(OwlsInsightConfig(api_key="owlsinsight_test_secret"))
    raw, health = provider.parse(_payload(), _board())
    assert health["mapped_games"] == 1
    ann = annotate_sharp_money_signals(raw, _board())
    spread = ann[ann["Market Type"].eq("spread")]
    assert set(spread["Ticket Leader"]) == {"Duke"}
    assert set(spread["Money Leader"]) == {"North Carolina"}
    assert set(spread["Sharp Side"]) == {"North Carolina"}
    assert spread["Sharp Gap Pts"].min() >= 20

    records = market_records(ann, actor="owner@example.com")
    spread_records = [r for r in records if r["market_type"] == "spread"]
    assert len(spread_records) == 2
    for row in spread_records:
        assert row["home_ticket_pct"] is not None
        assert row["away_ticket_pct"] is not None
        assert row["home_money_pct"] is not None
        assert row["away_money_pct"] is not None
        assert row["ticket_leader"] == "Duke"
        assert row["money_leader"] == "North Carolina"
        assert row["sharp_side"] == "North Carolina"
        assert row["sharp_gap_pts"] >= 20
        assert row["sharp_strength"] in {"strong", "very strong"}
        assert row["sharp_signal"] == "leader_flip"
        assert row["sharp_rule_version"] == "ticket_handle_gap_v1"


def test_private_history_roundtrip_keeps_persisted_diagnostics():
    rows = [{
        "slate_date": "2026-08-11",
        "game_id": "g1",
        "provider": "owlsinsight",
        "provider_game_id": "owls-g1",
        "market_type": "spread",
        "snapshot_time_utc": "2026-08-11T16:00:00+00:00",
        "snapshot_role": "observed",
        "sportsbook_scope": "draftkings",
        "source_label": "Owls Insight · DraftKings",
        "home_ticket_pct": 68,
        "away_ticket_pct": 32,
        "home_money_pct": 45,
        "away_money_pct": 55,
        "ticket_leader": "Duke",
        "money_leader": "North Carolina",
        "sharp_side": "North Carolina",
        "sharp_gap_pts": 23,
        "sharp_strength": "strong",
        "sharp_signal": "leader_flip",
        "sharp_read": "Money leads toward North Carolina even though more individual bets are on the other side.",
        "sharp_rule_version": "ticket_handle_gap_v1",
        "capture_trigger": "auto_admin",
        "raw_snapshot_hash": "abc",
    }]
    frame = snapshots_frame(rows)
    assert frame.iloc[0]["Sharp Side"] == "North Carolina"
    assert frame.iloc[0]["Sharp Gap Pts"] == 23
    assert frame.iloc[0]["Capture Trigger"] == "auto_admin"
    assert frame.iloc[0]["Ticket Leader"] == "Duke"


def test_v147_migration_keeps_archive_private_and_adds_diagnostics():
    sql = (ROOT / "supabase" / "market_terminal_v1_4_7.sql").read_text().lower()
    for col in [
        "ticket_leader text",
        "money_leader text",
        "sharp_side text",
        "sharp_gap_pts numeric",
        "sharp_strength text",
        "sharp_signal text",
        "sharp_read text",
        "sharp_rule_version text",
        "capture_trigger text",
    ]:
        assert col in sql
    assert "revoke all on table public.cbb_owner_betting_splits from anon, authenticated" in sql
    assert "grant all privileges on table public.cbb_owner_betting_splits to service_role" in sql
    assert "grant select on table public.cbb_owner_betting_splits to anon" not in sql


def test_admin_removes_historical_split_backfill_and_enables_live_archive():
    app = (ROOT / "app.py").read_text()
    assert 'APP_VERSION = "1.5.0"' in app
    assert "Historical Owls Insight backfill (MVP)" not in app
    assert "Backfill historical Owls betting splits" not in app
    assert "Capture live Owls betting splits now" in app
    assert "Auto-archive stale live splits on Admin Studio refresh" in app
    assert "latest_owner_split_capture_time" in app
    assert "capture_trigger" in app
    assert "/api/v1/history/public-betting" not in app
    provider_source = (ROOT / "cbb_dashboard" / "owlsinsight_provider.py").read_text()
    assert "/api/v1/history/public-betting" not in provider_source


def test_storage_requires_v147_columns_and_has_freshness_lookup():
    source = (ROOT / "cbb_dashboard" / "storage.py").read_text()
    assert 'select("slate_date,sharp_side,sharp_signal,capture_trigger")' in source
    assert "def latest_owner_split_capture_time" in source
    assert '.order("updated_at", desc=True)' in source


def test_model_firewall_and_public_percentage_firewall_remain():
    app = (ROOT / "app.py").read_text()
    assert "market-blind" in app
    assert "owner-only" in app.lower() or "private" in app.lower()
    assert "Public-safe output preview" in app
