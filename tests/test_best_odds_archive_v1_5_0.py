from __future__ import annotations

import pandas as pd

from cbb_dashboard.best_odds_archive import (
    archive_event_key,
    attach_best_odds_to_board,
    extract_best_odds_records,
)


def _book(key, title, home_spread, home_spread_price, away_spread, away_spread_price, home_ml, away_ml):
    return {
        "key": key,
        "title": title,
        "markets": [
            {
                "key": "spreads",
                "outcomes": [
                    {"name": "Duke", "point": home_spread, "price": home_spread_price},
                    {"name": "North Carolina", "point": away_spread, "price": away_spread_price},
                ],
            },
            {
                "key": "h2h",
                "outcomes": [
                    {"name": "Duke", "price": home_ml},
                    {"name": "North Carolina", "price": away_ml},
                ],
            },
        ],
    }


def _event():
    return {
        "id": "evt-1",
        "home_team": "Duke",
        "away_team": "North Carolina",
        "commence_time": "2026-11-14T01:00:00Z",
        "bookmakers": [
            _book("draftkings", "DraftKings", -4.5, -110, 4.5, -110, -210, 175),
            _book("fanduel", "FanDuel", -4.0, -115, 4.0, -105, -205, 180),
            _book("pinnacle", "Pinnacle", -4.5, -102, 4.5, -108, -208, 185),
        ],
    }


def test_best_spread_and_moneyline_are_selected_by_bettor_value():
    rows = extract_best_odds_records(
        _event(),
        captured_at="2026-11-13T20:00:00Z",
        response_timestamp="2026-11-13T19:59:58Z",
        snapshot_role="open",
    )
    by_market = {r["market_type"]: r for r in rows}
    spread = by_market["spread"]
    moneyline = by_market["moneyline"]

    assert spread["best_home_line"] == -4.0
    assert spread["best_home_book_key"] == "fanduel"
    # For the away side, +4.5 beats +4.0; among equal +4.5, -108 beats -110.
    assert spread["best_away_line"] == 4.5
    assert spread["best_away_price"] == -108
    assert spread["best_away_book_key"] == "pinnacle"
    assert moneyline["best_home_price"] == -205
    assert moneyline["best_home_book_key"] == "fanduel"
    assert moneyline["best_away_price"] == 185
    assert moneyline["best_away_book_key"] == "pinnacle"
    assert spread["book_count"] == 3
    assert len(spread["book_quotes"]) == 3
    dk = next(x for x in spread["book_quotes"] if x["book_key"] == "draftkings")
    assert dk["home_line"] == -4.5 and dk["away_line"] == 4.5


def test_equal_spread_prefers_better_price():
    event = _event()
    event["bookmakers"][1]["markets"][0]["outcomes"][0]["point"] = -4.5
    event["bookmakers"][1]["markets"][0]["outcomes"][0]["price"] = -105
    rows = extract_best_odds_records(event, captured_at="2026-11-13T20:00:00Z")
    spread = next(r for r in rows if r["market_type"] == "spread")
    assert spread["best_home_line"] == -4.5
    assert spread["best_home_price"] == -102
    assert spread["best_home_book_key"] == "pinnacle"


def test_archive_event_key_is_stable_and_board_independent():
    a = archive_event_key("Duke", "North Carolina", "2026-11-14T01:00:00Z")
    b = archive_event_key("Duke", "North Carolina", pd.Timestamp("2026-11-14 01:00:00+00:00"))
    assert a == b
    assert len(a) == 32


def test_attach_open_current_close_to_board():
    event = _event()
    open_rows = extract_best_odds_records(event, captured_at="2026-11-13T20:00:00Z", snapshot_role="open")
    # Current line moves from Duke -4 to Duke -5.
    current = _event()
    for book in current["bookmakers"]:
        for outcome in book["markets"][0]["outcomes"]:
            if outcome["name"] == "Duke":
                outcome["point"] -= 1.0
            else:
                outcome["point"] += 1.0
    current_rows = extract_best_odds_records(current, captured_at="2026-11-13T23:00:00Z", snapshot_role="observed")
    close_rows = extract_best_odds_records(current, captured_at="2026-11-14T00:50:00Z", snapshot_role="close")

    board = pd.DataFrame(
        [{
            "Game ID": "model-1",
            "Home Team": "Duke",
            "Away Team": "North Carolina",
            "Start Time UTC": "2026-11-14T01:00:00Z",
            "_start_dt": pd.Timestamp("2026-11-14T01:00:00Z"),
        }]
    )
    out = attach_best_odds_to_board(board, open_rows + current_rows + close_rows)
    row = out.iloc[0]
    assert row["_best_open_spread_home_line"] == -4.0
    assert row["_best_current_spread_home_line"] == -5.0
    assert row["_best_close_spread_home_line"] == -5.0
    assert row["_best_current_moneyline_home_book_key"] == "fanduel"
    assert int(row["_best_archive_snapshots"]) == 6


def test_swapped_provider_orientation_maps_back_to_board_home_away():
    event = _event()
    event["home_team"], event["away_team"] = event["away_team"], event["home_team"]
    # Outcomes still identify team names, so the provider event is simply orientation-swapped.
    rows = extract_best_odds_records(event, captured_at="2026-11-13T20:00:00Z", snapshot_role="open")
    board = pd.DataFrame(
        [{
            "Home Team": "Duke",
            "Away Team": "North Carolina",
            "Start Time UTC": "2026-11-14T01:00:00Z",
        }]
    )
    out = attach_best_odds_to_board(board, rows)
    row = out.iloc[0]
    # Provider away is Duke after the swap, and must map to board home.
    assert row["_best_current_spread_home_line"] == -4.0
    assert row["_best_current_spread_away_line"] == 4.5
