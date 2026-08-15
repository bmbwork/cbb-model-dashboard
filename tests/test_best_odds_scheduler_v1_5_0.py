from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "archive_owls_best_odds.py"
spec = importlib.util.spec_from_file_location("archive_owls_best_odds", SCRIPT)
archive = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(archive)


def _row(role="observed", commence="2026-11-14T01:00:00Z", captured="2026-11-14T00:00:00Z", market="spread"):
    return {
        "archive_event_key": "evt",
        "market_type": market,
        "snapshot_role": role,
        "commence_time_utc": commence,
        "captured_at_utc": captured,
        "best_home_line": -4.5 if market == "spread" else None,
        "best_home_price": -110,
        "best_home_book_key": "draftkings",
        "best_away_line": 4.5 if market == "spread" else None,
        "best_away_price": -110,
        "best_away_book_key": "draftkings",
        "raw_snapshot_hash": "oldhash",
    }


def test_due_close_only_when_pretip_and_close_missing():
    now = pd.Timestamp("2026-11-14T00:40:00Z")
    assert archive.due_close_keys([_row()], now) == {"evt"}
    assert archive.due_close_keys([_row(), _row(role="close")], now) == set()
    assert archive.due_close_keys([_row(commence="2026-11-14T03:00:00Z")], now) == set()


def test_finalize_missed_close_reuses_latest_real_pregame_quote():
    now = pd.Timestamp("2026-11-14T01:20:00Z")
    older = _row(captured="2026-11-13T23:00:00Z")
    latest = _row(captured="2026-11-14T00:17:00Z")
    result = archive.finalize_missed_closes([older, latest], now)
    assert len(result) == 1
    close = result[0]
    assert close["snapshot_role"] == "close"
    assert close["capture_trigger"] == "finalize_last_pregame"
    assert close["captured_at_utc"] == latest["captured_at_utc"]
    assert close["best_home_line"] == latest["best_home_line"]
    assert close["raw_snapshot_hash"] != latest["raw_snapshot_hash"]


def test_existing_spread_close_does_not_block_moneyline_close():
    now = pd.Timestamp("2026-11-14T01:20:00Z")
    rows = [
        _row(role="observed", captured="2026-11-14T00:17:00Z", market="spread"),
        _row(role="close", captured="2026-11-14T00:17:00Z", market="spread"),
        _row(role="observed", captured="2026-11-14T00:17:00Z", market="moneyline"),
    ]
    result = archive.finalize_missed_closes(rows, now)
    assert len(result) == 1
    assert result[0]["market_type"] == "moneyline"
    assert result[0]["snapshot_role"] == "close"
