from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

RANK_FILTER_ALL = "All games"
RANK_FILTER_ANY_TOP25 = "Any AP Top 25"
RANK_FILTER_ANY_TOP10 = "Any AP Top 10"
RANK_FILTER_MATCHUP = "Ranked vs ranked"
RANK_FILTERS = [RANK_FILTER_ALL, RANK_FILTER_ANY_TOP25, RANK_FILTER_ANY_TOP10, RANK_FILTER_MATCHUP]

MARKET_ANY = "Any market status"
MARKET_HAS_ML = "Has moneyline"
MARKET_HAS_SPREAD = "Has spread"
MARKET_HAS_BOTH = "Has ML + spread"
MARKET_FILTERS = [MARKET_ANY, MARKET_HAS_ML, MARKET_HAS_SPREAD, MARKET_HAS_BOTH]

MOVE_ANY = "Any movement"
MOVE_TOWARD = "Toward model pick"
MOVE_AWAY = "Away from model pick"
MOVE_1_PLUS = "Moved 1+ point"
MOVE_FILTERS = [MOVE_ANY, MOVE_TOWARD, MOVE_AWAY, MOVE_1_PLUS]

SORT_MODEL = "Model win chance"
SORT_TIME = "Tip time"
SORT_AP = "AP ranking"
SORT_ML = "Best ML price"
SORT_GAP = "Spread disagreement"
SORT_OPTIONS = [SORT_MODEL, SORT_TIME, SORT_AP, SORT_ML, SORT_GAP]


def _num(value: object) -> float:
    parsed = pd.to_numeric(value, errors="coerce")
    return float(parsed) if pd.notna(parsed) else float("nan")


def model_pick_side(row: pd.Series) -> str | None:
    pick = str(row.get("Model Pick") or "")
    if pick and pick == str(row.get("Home Team") or ""):
        return "home"
    if pick and pick == str(row.get("Away Team") or ""):
        return "away"
    return None


def model_pick_best_ml(row: pd.Series) -> float:
    side = model_pick_side(row)
    if side is None:
        return float("nan")
    return _num(row.get(f"_best_current_moneyline_{side}_price"))


def model_pick_best_spread(row: pd.Series) -> float:
    side = model_pick_side(row)
    if side is None:
        return float("nan")
    return _num(row.get(f"_best_current_spread_{side}_line"))


def model_pick_open_spread(row: pd.Series) -> float:
    side = model_pick_side(row)
    if side is None:
        return float("nan")
    return _num(row.get(f"_best_open_spread_{side}_line"))


def model_market_spread_gap(row: pd.Series) -> float:
    """Absolute difference between the independent model fair line and current best spread.

    Both fields are read from the model-pick team's perspective. This is a display/research
    filter only; it is not a bet recommendation and never enters the forecast.
    """
    market = model_pick_best_spread(row)
    fair = _num(row.get("Fair Spread"))
    if not np.isfinite(market) or not np.isfinite(fair):
        return float("nan")
    return abs(market - fair)


def spread_move_for_pick(row: pd.Series) -> float:
    """Current minus open from the model-pick perspective.

    Negative means the spread became less favorable to the model pick (market moved toward
    that team); positive means it became more favorable (market moved away from that team).
    """
    current = model_pick_best_spread(row)
    opening = model_pick_open_spread(row)
    if not np.isfinite(current) or not np.isfinite(opening):
        return float("nan")
    return current - opening


def best_ap_rank(row: pd.Series) -> float:
    values = [_num(row.get("Home Rank")), _num(row.get("Away Rank"))]
    usable = [v for v in values if np.isfinite(v) and v > 0]
    return min(usable) if usable else float("nan")


def _rank_mask(frame: pd.DataFrame, mode: str) -> pd.Series:
    home = pd.to_numeric(frame.get("Home Rank", pd.Series(np.nan, index=frame.index)), errors="coerce")
    away = pd.to_numeric(frame.get("Away Rank", pd.Series(np.nan, index=frame.index)), errors="coerce")
    home25 = home.between(1, 25, inclusive="both")
    away25 = away.between(1, 25, inclusive="both")
    if mode == RANK_FILTER_ANY_TOP25:
        return home25 | away25
    if mode == RANK_FILTER_ANY_TOP10:
        return home.between(1, 10, inclusive="both") | away.between(1, 10, inclusive="both")
    if mode == RANK_FILTER_MATCHUP:
        return home25 & away25
    if mode != RANK_FILTER_ALL:
        raise ValueError(f"Unsupported ranking filter: {mode}")
    return pd.Series(True, index=frame.index)


def enrich_filter_fields(board: pd.DataFrame) -> pd.DataFrame:
    if board is None or board.empty:
        return board.copy() if isinstance(board, pd.DataFrame) else pd.DataFrame()
    out = board.copy()
    out["_filter_best_ml"] = out.apply(model_pick_best_ml, axis=1)
    out["_filter_best_spread"] = out.apply(model_pick_best_spread, axis=1)
    out["_filter_spread_gap"] = out.apply(model_market_spread_gap, axis=1)
    out["_filter_spread_move"] = out.apply(spread_move_for_pick, axis=1)
    out["_filter_ap_rank"] = out.apply(best_ap_rank, axis=1)
    return out


def filter_board(
    board: pd.DataFrame,
    *,
    teams: Iterable[str] | None = None,
    ranking_mode: str = RANK_FILTER_ALL,
    min_win_probability: float = 0.50,
    ml_range_enabled: bool = False,
    ml_min: int = -350,
    ml_max: int = 500,
    market_mode: str = MARKET_ANY,
    min_spread_gap: float = 0.0,
    movement_mode: str = MOVE_ANY,
    min_data_quality: float = 0.0,
    verified_only: bool = False,
    d1_only: bool = False,
    venue_mode: str = "All venues",
    sort_by: str = SORT_MODEL,
) -> pd.DataFrame:
    """Apply display-only discovery filters to an already-published immutable slate."""
    if board is None or board.empty:
        return board.copy() if isinstance(board, pd.DataFrame) else pd.DataFrame()
    if int(ml_min) > int(ml_max):
        raise ValueError("Moneyline minimum cannot exceed maximum")
    if market_mode not in MARKET_FILTERS:
        raise ValueError(f"Unsupported market filter: {market_mode}")
    if movement_mode not in MOVE_FILTERS:
        raise ValueError(f"Unsupported movement filter: {movement_mode}")
    if sort_by not in SORT_OPTIONS:
        raise ValueError(f"Unsupported sort: {sort_by}")

    out = enrich_filter_fields(board)
    team_values = {str(x) for x in (teams or []) if str(x).strip()}
    if team_values:
        home = out.get("Home Team", pd.Series("", index=out.index)).astype(str)
        away = out.get("Away Team", pd.Series("", index=out.index)).astype(str)
        out = out.loc[home.isin(team_values) | away.isin(team_values)]

    out = out.loc[_rank_mask(out, ranking_mode)]

    win = pd.to_numeric(out.get("_win_prob", out.get("Win Probability", pd.Series(np.nan, index=out.index))), errors="coerce")
    out = out.loc[win >= float(min_win_probability)]

    if ml_range_enabled:
        ml = pd.to_numeric(out["_filter_best_ml"], errors="coerce")
        out = out.loc[ml.notna() & ml.between(float(ml_min), float(ml_max), inclusive="both")]

    has_ml = pd.to_numeric(out["_filter_best_ml"], errors="coerce").notna()
    has_spread = pd.to_numeric(out["_filter_best_spread"], errors="coerce").notna()
    if market_mode == MARKET_HAS_ML:
        out = out.loc[has_ml]
    elif market_mode == MARKET_HAS_SPREAD:
        out = out.loc[has_spread]
    elif market_mode == MARKET_HAS_BOTH:
        out = out.loc[has_ml & has_spread]

    if float(min_spread_gap) > 0:
        gap = pd.to_numeric(out["_filter_spread_gap"], errors="coerce")
        out = out.loc[gap.notna() & (gap >= float(min_spread_gap))]

    move = pd.to_numeric(out["_filter_spread_move"], errors="coerce")
    if movement_mode == MOVE_TOWARD:
        out = out.loc[move.notna() & (move < -0.05)]
    elif movement_mode == MOVE_AWAY:
        out = out.loc[move.notna() & (move > 0.05)]
    elif movement_mode == MOVE_1_PLUS:
        out = out.loc[move.notna() & (move.abs() >= 1.0)]

    quality = pd.to_numeric(out.get("Data Quality", pd.Series(np.nan, index=out.index)), errors="coerce")
    if float(min_data_quality) > 0:
        out = out.loc[quality.notna() & (quality >= float(min_data_quality))]

    if verified_only:
        verified = out.get("_availability_verified", out.get("Availability Verified", pd.Series(False, index=out.index)))
        out = out.loc[verified.fillna(False).astype(bool)]

    if d1_only:
        d1 = out.get("_is_d1", out.get("D1 Evaluation Eligible", pd.Series(False, index=out.index)))
        out = out.loc[d1.fillna(False).astype(bool)]

    if venue_mode == "Neutral court only":
        neutral = out.get("_neutral", out.get("Neutral Site", pd.Series(False, index=out.index)))
        out = out.loc[neutral.fillna(False).astype(bool)]
    elif venue_mode == "Campus / scheduled site only":
        neutral = out.get("_neutral", out.get("Neutral Site", pd.Series(False, index=out.index)))
        out = out.loc[~neutral.fillna(False).astype(bool)]
    elif venue_mode != "All venues":
        raise ValueError(f"Unsupported venue filter: {venue_mode}")

    if sort_by == SORT_MODEL:
        out = out.assign(_sort=pd.to_numeric(out.get("_win_prob", out.get("Win Probability")), errors="coerce")).sort_values("_sort", ascending=False, na_position="last")
    elif sort_by == SORT_TIME:
        out = out.assign(_sort=pd.to_datetime(out.get("_start_dt", out.get("Start Time UTC")), utc=True, errors="coerce")).sort_values("_sort", ascending=True, na_position="last")
    elif sort_by == SORT_AP:
        out = out.sort_values(["_filter_ap_rank", "_filter_best_ml"], ascending=[True, False], na_position="last")
    elif sort_by == SORT_ML:
        out = out.sort_values("_filter_best_ml", ascending=False, na_position="last")
    elif sort_by == SORT_GAP:
        out = out.sort_values("_filter_spread_gap", ascending=False, na_position="last")

    return out.drop(columns=["_sort"], errors="ignore").reset_index(drop=True)
