from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


REQUIRED_V11_COLUMNS = [
    "Game ID", "Away Team", "Home Team", "Model Pick", "Win Probability",
    "Projected Away Score", "Projected Home Score", "Fair Spread", "Fair Moneyline",
    "Model Version", "Target Date", "Game Classification", "D1 Evaluation Eligible",
    "Schedule Translation Margin Adj", "V1.0.1 Baseline Pick",
    "V1.0.1 Baseline Win Probability", "V1.0.1 Baseline Fair Spread",
]

GRADE_REQUIRED_COLUMNS = [
    "Game ID", "Target Date", "Status", "Final Away Score", "Final Home Score",
    "Grade Eligible", "Actual Winner", "Model Winner Correct", "Absolute Margin Error",
    "Brier Component", "Log Loss Component",
]

DECISION_HOME_SPREAD_COLUMNS = (
    "Bet Home Spread", "Taken Home Spread", "Decision Home Spread", "Market Home Spread", "Sportsbook Home Spread",
)
CLOSING_HOME_SPREAD_COLUMNS = ("Closing Home Spread",)
EXPLICIT_SPREAD_RESULT_COLUMNS = (
    "Model Spread Correct", "Spread Correct", "ATS Correct", "Model ATS Correct",
)


@dataclass(frozen=True)
class BoardReport:
    slate_date: str
    model_version: str
    rows: int
    d1_games: int
    warnings: tuple[str, ...]


class DataValidationError(ValueError):
    pass


def read_csv(source: Any) -> pd.DataFrame:
    return pd.read_csv(source)


def _single_text(frame: pd.DataFrame, column: str) -> str:
    vals = frame[column].dropna().astype(str).str.strip()
    vals = vals[vals.ne("")].unique().tolist()
    if len(vals) != 1:
        raise DataValidationError(f"Expected exactly one {column}; found {vals or 'none'}.")
    return vals[0]


def _bool_scalar(value: Any) -> bool | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, float, np.number)) and float(value) in (0.0, 1.0):
        return bool(int(value))
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "w", "win", "won"}:
        return True
    if text in {"false", "0", "no", "n", "l", "loss", "lost"}:
        return False
    return None


def _bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(False)
    mapping = {
        "true": True, "1": True, "yes": True, "y": True,
        "false": False, "0": False, "no": False, "n": False,
    }
    return series.map(lambda x: mapping.get(str(x).strip().lower(), bool(x) if pd.notna(x) else False)).astype(bool)


def _nullable_bool_series(series: pd.Series) -> pd.Series:
    return series.map(_bool_scalar).astype("boolean")


def _numeric(frame: pd.DataFrame, columns: list[str]) -> None:
    for col in columns:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")


def _first_numeric_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> tuple[pd.Series, str | None]:
    for col in candidates:
        if col in frame.columns:
            return pd.to_numeric(frame[col], errors="coerce"), col
    return pd.Series(np.nan, index=frame.index, dtype=float), None


def normalize_board(frame: pd.DataFrame) -> tuple[pd.DataFrame, BoardReport]:
    if frame is None or frame.empty:
        raise DataValidationError("Decision board is empty.")
    board = frame.copy()
    board.columns = [str(c).strip() for c in board.columns]
    missing = [c for c in REQUIRED_V11_COLUMNS if c not in board.columns]
    if missing:
        raise DataValidationError("Missing CBB 1.1.x decision-board columns: " + ", ".join(missing))

    slate_date = _single_text(board, "Target Date")
    try:
        slate_date = pd.to_datetime(slate_date).date().isoformat()
    except Exception as exc:
        raise DataValidationError(f"Target Date is not a valid date: {slate_date}") from exc

    model_version = _single_text(board, "Model Version")
    if not model_version.startswith("1.1"):
        raise DataValidationError(f"Champion Terminal expects a compatible 1.1.x board; received {model_version}.")

    if board["Game ID"].isna().any() or board["Game ID"].duplicated().any():
        raise DataValidationError("Game ID must be present and unique for every row.")

    numeric_columns = [
        "Rank", "D1 Rank", "Win Probability", "Confidence Score", "Projected Away Score",
        "Projected Home Score", "Projected Total", "Projected Winner Margin", "Fair Spread",
        "Fair Moneyline", "Home Win Probability", "Away Win Probability", "Fair Home Spread",
        "Fair Home Moneyline", "Fair Away Moneyline", "Margin SD", "Home Margin P10", "Home Margin P90",
        "V1.0.1 Baseline Rank", "V1.0.1 Baseline D1 Rank", "V1.0.1 Baseline Win Probability",
        "V1.0.1 Baseline Confidence Score", "V1.0.1 Baseline Projected Away Score",
        "V1.0.1 Baseline Projected Home Score", "V1.0.1 Baseline Projected Total",
        "V1.0.1 Baseline Projected Winner Margin", "V1.0.1 Baseline Fair Spread",
        "V1.0.1 Baseline Fair Moneyline", "V1.0.1 Baseline Home Win Probability",
        "Schedule Translation Margin Adj", "Schedule Translation Raw Adj", "Schedule Translation Linear Beta",
        "Schedule Translation Hinge Beta", "Schedule Translation Training Games", "Expected Pace", "Home AdjO",
        "Home AdjD", "Home AdjNet", "Away AdjO", "Away AdjD", "Away AdjNet", "Home SOS", "Away SOS",
        "V1.1 Home D1 SOS", "V1.1 Away D1 SOS", "Home D1 SOS", "Away D1 SOS", "SOS Difference Home-Away",
        "Home Matchup Adj /100", "Away Matchup Adj /100", "Home Availability Adj", "Away Availability Adj",
        "Data Quality", "Minutes Before Tip", "Champion Baseline Home Margin", "Champion Calibrated Home Margin",
        "Champion Margin Calibration Adj", "Champion Training Games", "Champion Training Dates",
        "V1.1.3B Margin Adjustment", "V1.1.3B Training Games",
        "Home PPG", "Away PPG", "Home PPG Allowed", "Away PPG Allowed",
        "Home Points Per Game", "Away Points Per Game", "Home Points Allowed Per Game", "Away Points Allowed Per Game",
        *DECISION_HOME_SPREAD_COLUMNS, *CLOSING_HOME_SPREAD_COLUMNS,
    ]
    _numeric(board, numeric_columns)

    for col in ["D1 Evaluation Eligible", "Home D1", "Away D1", "Neutral Site", "Availability Verified", "Deployment Eligible", "Schedule Translation Applied"]:
        if col in board.columns:
            board[col] = _bool_series(board[col])

    p = board["Win Probability"]
    if p.isna().any() or ((p < 0.5) | (p > 1.0)).any():
        raise DataValidationError("Win Probability must be between 0.50 and 1.00 for every game.")

    board["_rank"] = pd.to_numeric(board.get("Rank", pd.Series(index=board.index, dtype=float)), errors="coerce")
    if board["_rank"].isna().all():
        board["_rank"] = np.arange(1, len(board) + 1)
    board["_d1_rank"] = pd.to_numeric(board.get("D1 Rank", pd.Series(index=board.index, dtype=float)), errors="coerce")
    board["_is_d1"] = _bool_series(board["D1 Evaluation Eligible"])
    board["_win_prob"] = pd.to_numeric(board["Win Probability"], errors="coerce")
    board["_translation"] = pd.to_numeric(board.get("Schedule Translation Margin Adj", 0), errors="coerce").fillna(0.0)
    champion_adj = pd.to_numeric(board.get("Champion Margin Calibration Adj", pd.Series(np.nan, index=board.index)), errors="coerce")
    fallback_b = pd.to_numeric(board.get("V1.1.3B Margin Adjustment", pd.Series(np.nan, index=board.index)), errors="coerce")
    board["_champion_adj"] = champion_adj.where(champion_adj.notna(), fallback_b)
    board["_display_adj"] = board["_champion_adj"].where(board["_champion_adj"].notna(), board["_translation"])
    board["_data_quality"] = pd.to_numeric(board.get("Data Quality", np.nan), errors="coerce")
    board["_availability_verified"] = _bool_series(board.get("Availability Verified", pd.Series(False, index=board.index)))
    board["_neutral"] = _bool_series(board.get("Neutral Site", pd.Series(False, index=board.index)))
    board["_baseline_prob"] = pd.to_numeric(board.get("V1.0.1 Baseline Win Probability", np.nan), errors="coerce")
    board["_baseline_pick"] = board.get("V1.0.1 Baseline Pick", "").fillna("").astype(str)
    board["_pick_changed"] = board["Model Pick"].astype(str).ne(board["_baseline_pick"])
    board["_game_label"] = board["Away Team"].astype(str) + " @ " + board["Home Team"].astype(str)
    board["_is_champion"] = board["Model Version"].astype(str).str.upper().eq("1.1.3B")

    if "Start Time UTC" in board.columns:
        board["_start_dt"] = pd.to_datetime(board["Start Time UTC"], errors="coerce", utc=True)
    else:
        board["_start_dt"] = pd.NaT

    # Result placeholders are present on every board so card rendering remains simple.
    board["_grade_eligible"] = False
    board["_final_away"] = np.nan
    board["_final_home"] = np.nan
    board["_actual_winner"] = ""
    board["_ml_correct"] = pd.Series([pd.NA] * len(board), dtype="boolean")
    board["_spread_correct"] = pd.Series([pd.NA] * len(board), dtype="boolean")
    market_home, market_source = _first_numeric_column(board, DECISION_HOME_SPREAD_COLUMNS)
    closing_home, closing_source = _first_numeric_column(board, CLOSING_HOME_SPREAD_COLUMNS)
    board["_market_home_spread"] = market_home
    board["_spread_source"] = market_source or ""
    board["_closing_home_spread"] = closing_home
    board["_closing_source"] = closing_source or ""

    warnings: list[str] = []
    if not board["_availability_verified"].any():
        warnings.append("Player availability is unverified across this slate; player-impact adjustments should be read cautiously.")
    non_d1 = int((~board["_is_d1"]).sum())
    if non_d1:
        warnings.append(f"{non_d1} game(s) are excluded from the primary D-I vs D-I evaluation cohort.")
    if (board["_data_quality"].dropna() < 50).any():
        warnings.append("At least one game has Data Quality below 50.")

    board = board.sort_values(["_rank", "_win_prob"], ascending=[True, False], kind="stable").reset_index(drop=True)
    report = BoardReport(
        slate_date=slate_date,
        model_version=model_version,
        rows=len(board),
        d1_games=int(board["_is_d1"].sum()),
        warnings=tuple(warnings),
    )
    return board, report


def normalize_graded_board(frame: pd.DataFrame) -> tuple[pd.DataFrame, BoardReport]:
    board, report = normalize_board(frame)
    missing = [c for c in GRADE_REQUIRED_COLUMNS if c not in board.columns]
    if missing:
        raise DataValidationError("Missing graded-board columns: " + ", ".join(missing))
    _numeric(board, [
        "Final Away Score", "Final Home Score", "Actual Home Margin", "Actual Total",
        "Margin Error", "Absolute Margin Error", "Total Error", "Absolute Total Error", "Brier Component", "Log Loss Component",
        "V1.0.1 Baseline Margin Error", "V1.0.1 Baseline Absolute Margin Error", "V1.0.1 Baseline Brier Component",
        "V1.0.1 Baseline Log Loss Component", "V1.1 Margin Error Improvement",
        *DECISION_HOME_SPREAD_COLUMNS, *CLOSING_HOME_SPREAD_COLUMNS,
    ])
    for col in ["Grade Eligible", "Primary Evaluation Eligible"]:
        if col in board.columns:
            board[col] = _bool_series(board[col])

    board["_grade_eligible"] = _bool_series(board["Grade Eligible"])
    board["_final_away"] = pd.to_numeric(board["Final Away Score"], errors="coerce")
    board["_final_home"] = pd.to_numeric(board["Final Home Score"], errors="coerce")
    board["_actual_winner"] = board["Actual Winner"].fillna("").astype(str)
    board["_ml_correct"] = _nullable_bool_series(board["Model Winner Correct"])

    explicit_result = None
    explicit_source = None
    for col in EXPLICIT_SPREAD_RESULT_COLUMNS:
        if col in board.columns:
            explicit_result = _nullable_bool_series(board[col])
            explicit_source = col
            break

    market_home, market_source = _first_numeric_column(board, DECISION_HOME_SPREAD_COLUMNS)
    closing_home, closing_source = _first_numeric_column(board, CLOSING_HOME_SPREAD_COLUMNS)
    board["_closing_home_spread"] = closing_home
    board["_closing_source"] = closing_source or ""
    board["_market_home_spread"] = market_home
    if explicit_result is not None:
        board["_spread_correct"] = explicit_result
        board["_spread_source"] = explicit_source or ""
    elif market_source:
        actual_home_margin = pd.to_numeric(board.get("Actual Home Margin"), errors="coerce")
        ats_margin = actual_home_margin + market_home
        pick_home = board["Model Pick"].astype(str).eq(board["Home Team"].astype(str))
        pick_away = board["Model Pick"].astype(str).eq(board["Away Team"].astype(str))
        result = pd.Series(pd.NA, index=board.index, dtype="boolean")
        valid = board["_grade_eligible"] & ats_margin.notna() & market_home.notna() & ats_margin.ne(0)
        result.loc[valid & pick_home] = ats_margin.loc[valid & pick_home] > 0
        result.loc[valid & pick_away] = ats_margin.loc[valid & pick_away] < 0
        board["_spread_correct"] = result
        board["_spread_source"] = market_source
    else:
        board["_spread_correct"] = pd.Series(pd.NA, index=board.index, dtype="boolean")
        board["_spread_source"] = ""
    return board, report


def attach_grading(board: pd.DataFrame, grading: pd.DataFrame | None) -> pd.DataFrame:
    """Attach official result fields to an already-normalized prediction board.

    Grading is display-only. The original prediction values are never overwritten.
    ATS is graded only from an explicit result field or a stored decision/taken
    sportsbook spread. Closing spread is retained separately for CLV reference and
    model fair spread is never treated as a sportsbook line.
    """
    if grading is None or grading.empty:
        return board.copy()
    graded, _ = normalize_graded_board(grading)
    result_cols = [
        "Game ID", "_grade_eligible", "_final_away", "_final_home", "_actual_winner",
        "_ml_correct", "_spread_correct", "_market_home_spread", "_spread_source", "_closing_home_spread", "_closing_source",
    ]
    right = graded[result_cols].copy()
    left = board.copy()
    left["__gid"] = left["Game ID"].astype(str)
    right["__gid"] = right["Game ID"].astype(str)
    right = right.drop(columns=["Game ID"])
    # Drop placeholders so merge cannot create duplicated columns.
    placeholders = [c for c in result_cols if c != "Game ID" and c in left.columns]
    left = left.drop(columns=placeholders)
    out = left.merge(right, on="__gid", how="left", validate="one_to_one").drop(columns=["__gid"])
    out["_grade_eligible"] = out["_grade_eligible"].fillna(False).astype(bool)
    for col in ["_ml_correct", "_spread_correct"]:
        out[col] = out[col].astype("boolean")
    out["_spread_source"] = out["_spread_source"].fillna("")
    out["_closing_source"] = out["_closing_source"].fillna("")
    return out


def board_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Bettor-facing decision table with research plumbing removed."""
    wanted = [
        "Rank", "D1 Rank", "Away Team", "Home Team", "Neutral Site", "Game Classification",
        "Model Pick", "Win Probability", "Projected Away Score", "Projected Home Score",
        "Fair Spread", "Fair Moneyline", "Projected Total", "Expected Pace", "Margin SD",
        "Home Margin P10", "Home Margin P90", "Home AdjO", "Home AdjD", "Home AdjNet",
        "Away AdjO", "Away AdjD", "Away AdjNet", "V1.1 Home D1 SOS", "V1.1 Away D1 SOS",
        "Home SOS", "Away SOS", "Home PPG", "Away PPG", "Home PPG Allowed", "Away PPG Allowed",
        "Home Matchup Adj /100", "Away Matchup Adj /100", "Data Quality", "Availability Verified",
        *DECISION_HOME_SPREAD_COLUMNS, *CLOSING_HOME_SPREAD_COLUMNS,
    ]
    return frame[[c for c in wanted if c in frame.columns]].copy()


def json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if pd.isna(value) if not isinstance(value, (list, dict, tuple, set)) else False:
        return None
    return value


def dataframe_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw in frame.to_dict(orient="records"):
        records.append({str(k): json_safe(v) for k, v in raw.items() if not str(k).startswith("_")})
    return records
