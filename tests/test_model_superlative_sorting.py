import numpy as np
import pandas as pd
import pytest

from cbb_dashboard.board_filters import (
    SORT_OPTIONS, SORT_SPREAD_HIGH, SORT_SPREAD_LOW, SORT_TOTAL_HIGH,
    SORT_TOTAL_LOW, SORT_FAIR_HIGH, SORT_FAIR_LOW, filter_board,
)


def _board():
    rows = []
    for name, spread, total, probability, odds, kickoff in [
        ("a", -3, 160, .6, -150, "2026-11-14T21:00:00Z"),
        ("b", -12, 140, .75, -300, "2026-11-14T20:00:00Z"),
        ("c", 7, 180, 2 / 3, -200, "2026-11-14T22:00:00Z"),
        ("d", -12, 140, .75, -300, "2026-11-14T23:00:00Z"),
        ("missing", np.inf, "unavailable", 1., None, "2026-11-14T18:00:00Z"),
    ]:
        rows.append({"Game ID": name, "Home Team": f"Home {name}", "Away Team": f"Away {name}",
                     "Model Pick": f"Home {name}", "Win Probability": probability,
                     "Fair Spread": spread, "Projected Total": total, "Fair Moneyline": odds,
                     "Start Time UTC": kickoff, "Rank": len(rows) + 1})
    return pd.DataFrame(rows)


@pytest.mark.parametrize("choice, expected", [
    (SORT_SPREAD_HIGH, ["b", "d", "c", "a", "missing"]),
    (SORT_SPREAD_LOW, ["a", "c", "b", "d", "missing"]),
    (SORT_TOTAL_HIGH, ["c", "a", "b", "d", "missing"]),
    (SORT_TOTAL_LOW, ["b", "d", "a", "c", "missing"]),
    (SORT_FAIR_HIGH, ["a", "c", "b", "d", "missing"]),
    (SORT_FAIR_LOW, ["b", "d", "c", "a", "missing"]),
])
def test_all_six_model_sorts_order_published_values_without_changing_forecasts(choice, expected):
    board = _board()
    original = board.copy(deep=True)
    result = filter_board(board, sort_by=choice)
    assert choice in SORT_OPTIONS
    assert result["Game ID"].tolist() == expected
    pd.testing.assert_frame_equal(board, original)
    # Every original forecast, market field and rank survives unchanged.
    pd.testing.assert_frame_equal(
        result.set_index("Game ID")[board.columns.drop("Game ID")].sort_index(),
        original.set_index("Game ID").sort_index(),
    )


def test_metric_ties_use_time_then_team_and_remain_stable_with_missing_kickoff():
    board = _board().iloc[:4].copy()
    board["Fair Spread"] = -7
    board["Start Time UTC"] = [None, "2026-11-14T20:00:00Z", "2026-11-14T20:00:00Z", "2026-11-14T20:00:00Z"]
    board["Away Team"] = ["A", "Z", "B", "B"]
    board["Home Team"] = ["A", "X", "Z", "A"]
    choice = SORT_SPREAD_HIGH
    result = filter_board(board, sort_by=choice)
    assert result["Game ID"].tolist() == ["d", "c", "b", "a"]


@pytest.mark.parametrize("invalid", [None, "invalid", np.inf, -np.inf, -1])
def test_invalid_totals_are_last_for_both_directions(invalid):
    board = _board().iloc[:2].copy()
    board["Projected Total"] = board["Projected Total"].astype(object)
    board.loc[0, "Projected Total"] = invalid
    for choice in (SORT_TOTAL_HIGH, SORT_TOTAL_LOW):
        result = filter_board(board, sort_by=choice)
        assert result["Game ID"].tolist() == ["b", "a"]


@pytest.mark.parametrize("invalid", [None, "invalid", np.inf, -np.inf, 0, 50, -99])
def test_invalid_american_odds_are_last(invalid):
    board = _board().iloc[:2].copy()
    board["Fair Moneyline"] = board["Fair Moneyline"].astype(object)
    board.loc[0, "Fair Moneyline"] = invalid
    for choice in (SORT_FAIR_HIGH, SORT_FAIR_LOW):
        assert filter_board(board, sort_by=choice)["Game ID"].tolist() == ["b", "a"]
