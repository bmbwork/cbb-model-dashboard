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


def _bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(False)
    mapping = {
        "true": True, "1": True, "yes": True, "y": True,
        "false": False, "0": False, "no": False, "n": False,
    }
    return series.map(lambda x: mapping.get(str(x).strip().lower(), bool(x) if pd.notna(x) else False)).astype(bool)


def _numeric(frame: pd.DataFrame, columns: list[str]) -> None:
    for col in columns:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")


def normalize_board(frame: pd.DataFrame) -> tuple[pd.DataFrame, BoardReport]:
    if frame is None or frame.empty:
        raise DataValidationError("Decision board is empty.")
    board = frame.copy()
    board.columns = [str(c).strip() for c in board.columns]
    missing = [c for c in REQUIRED_V11_COLUMNS if c not in board.columns]
    if missing:
        raise DataValidationError("Missing V1.1 decision-board columns: " + ", ".join(missing))

    slate_date = _single_text(board, "Target Date")
    try:
        slate_date = pd.to_datetime(slate_date).date().isoformat()
    except Exception as exc:
        raise DataValidationError(f"Target Date is not a valid date: {slate_date}") from exc

    model_version = _single_text(board, "Model Version")
    if not model_version.startswith("1.1"):
        raise DataValidationError(f"Intelligence Terminal V1.1 expects a 1.1.x challenger board; received {model_version}.")

    if board["Game ID"].isna().any() or board["Game ID"].duplicated().any():
        raise DataValidationError("Game ID must be present and unique for every row.")

    _numeric(board, [
        "Rank", "D1 Rank", "Win Probability", "Confidence Score", "Projected Away Score",
        "Projected Home Score", "Projected Total", "Projected Winner Margin", "Fair Spread",
        "Fair Moneyline", "Home Win Probability", "Away Win Probability", "Fair Home Spread",
        "Fair Home Moneyline", "Fair Away Moneyline", "Margin SD", "Home Margin P10", "Home Margin P90",
        "V1.0.1 Baseline Rank", "V1.0.1 Baseline D1 Rank", "V1.0.1 Baseline Win Probability",
        "V1.0.1 Baseline Confidence Score", "V1.0.1 Baseline Projected Away Score",
        "V1.0.1 Baseline Projected Home Score", "V1.0.1 Baseline Projected Total",
        "V1.0.1 Baseline Projected Winner Margin", "V1.0.1 Baseline Fair Spread",
        "V1.0.1 Baseline Fair Moneyline", "Schedule Translation Margin Adj",
        "Schedule Translation Raw Adj", "Schedule Translation Linear Beta", "Schedule Translation Hinge Beta",
        "Schedule Translation Training Games", "Expected Pace", "Home AdjO", "Home AdjD", "Home AdjNet",
        "Away AdjO", "Away AdjD", "Away AdjNet", "Home SOS", "Away SOS", "V1.1 Home D1 SOS",
        "V1.1 Away D1 SOS", "SOS Difference Home-Away", "Home Matchup Adj /100", "Away Matchup Adj /100",
        "Home Availability Adj", "Away Availability Adj", "Data Quality", "Minutes Before Tip",
    ])

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
    board["_data_quality"] = pd.to_numeric(board.get("Data Quality", np.nan), errors="coerce")
    board["_availability_verified"] = _bool_series(board.get("Availability Verified", pd.Series(False, index=board.index)))
    board["_neutral"] = _bool_series(board.get("Neutral Site", pd.Series(False, index=board.index)))
    board["_baseline_prob"] = pd.to_numeric(board.get("V1.0.1 Baseline Win Probability", np.nan), errors="coerce")
    board["_baseline_pick"] = board.get("V1.0.1 Baseline Pick", "").fillna("").astype(str)
    board["_pick_changed"] = board["Model Pick"].astype(str).ne(board["_baseline_pick"])
    board["_game_label"] = board["Away Team"].astype(str) + " @ " + board["Home Team"].astype(str)

    if "Start Time UTC" in board.columns:
        board["_start_dt"] = pd.to_datetime(board["Start Time UTC"], errors="coerce", utc=True)
    else:
        board["_start_dt"] = pd.NaT

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
        "Model Winner Correct", "Margin Error", "Absolute Margin Error", "Total Error",
        "Absolute Total Error", "Brier Component", "Log Loss Component",
        "V1.0.1 Baseline Winner Correct", "V1.0.1 Baseline Margin Error",
        "V1.0.1 Baseline Absolute Margin Error", "V1.0.1 Baseline Brier Component",
        "V1.0.1 Baseline Log Loss Component", "V1.1 Margin Error Improvement",
    ])
    for col in ["Grade Eligible", "Primary Evaluation Eligible"]:
        if col in board.columns:
            board[col] = _bool_series(board[col])
    return board, report


def board_table(frame: pd.DataFrame) -> pd.DataFrame:
    wanted = [
        "Rank", "D1 Rank", "Away Team", "Home Team", "Neutral Site", "Game Classification",
        "Model Pick", "Win Probability", "Projected Away Score", "Projected Home Score",
        "Fair Spread", "Fair Moneyline", "Projected Total", "Expected Pace", "Confidence Score",
        "Schedule Translation Margin Adj", "V1.0.1 Baseline Pick", "V1.0.1 Baseline Win Probability",
        "V1.0.1 Baseline Fair Spread", "Home AdjNet", "Away AdjNet", "V1.1 Home D1 SOS",
        "V1.1 Away D1 SOS", "Data Quality", "Availability Verified",
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
