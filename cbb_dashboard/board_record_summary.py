"""CFB-style Game Board summary values for CBB.

Sportsbook ATS grades take priority. When an older saved slate has no persisted
sportsbook spread grade, the spread card evaluates the frozen model fair line and
labels that provenance explicitly rather than leaving the record blank.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _record(correct: pd.Series) -> tuple[str, int]:
    known = correct.dropna().astype(bool)
    if known.empty:
        return "—", 0
    wins = int(known.sum())
    losses = int(len(known) - wins)
    return f"{wins}-{losses}", int(len(known))


def _record_text(wins: int, losses: int, pushes: int = 0) -> str:
    if wins + losses + pushes == 0:
        return "—"
    return f"{wins}-{losses}" + (f"-{pushes}P" if pushes else "")


def _model_spread_record(board: pd.DataFrame, eligible: pd.Series) -> tuple[str, int]:
    wins = losses = pushes = 0
    for idx, row in board.loc[eligible].iterrows():
        line = _number(row.get("Fair Spread"))
        home = _number(row.get("_final_home"))
        away = _number(row.get("_final_away"))
        pick = str(row.get("Model Pick") or "")
        home_team = str(row.get("Home Team") or "")
        away_team = str(row.get("Away Team") or "")
        if line is None or home is None or away is None or pick not in {home_team, away_team}:
            continue
        if min(home, away) < 0 or not home.is_integer() or not away.is_integer():
            continue
        margin = home - away if pick == home_team else away - home
        clearance = margin + line
        if abs(clearance) < 1e-9:
            pushes += 1
        elif clearance > 0:
            wins += 1
        else:
            losses += 1
    count = wins + losses + pushes
    return _record_text(wins, losses, pushes), count


def _market_coverage(board: pd.DataFrame) -> int:
    if board.empty:
        return 0
    ml = pd.to_numeric(board.get("_filter_best_ml", pd.Series(index=board.index, dtype=float)), errors="coerce")
    spread = pd.to_numeric(board.get("_filter_best_spread", pd.Series(index=board.index, dtype=float)), errors="coerce")
    return int((ml.notna() | spread.notna()).sum())


def summary_cards(board: pd.DataFrame) -> list[tuple[str, str, str]]:
    if board is None or board.empty:
        return []

    probs = pd.to_numeric(board.get("_win_prob", board.get("Win Probability")), errors="coerce")
    usable = probs.dropna()
    if usable.empty:
        strongest, strongest_note, average = "—", "probability unavailable", "—"
    else:
        idx = usable.idxmax()
        strongest = str(board.loc[idx].get("Model Pick") or "—")
        strongest_note = f"{usable.loc[idx] * 100:.1f}% win chance"
        average = f"{usable.mean() * 100:.0f}%"

    eligible = board.get("_grade_eligible", pd.Series(False, index=board.index)).fillna(False).astype(bool)
    ml_series = board.get("_ml_correct", pd.Series(pd.NA, index=board.index, dtype="boolean")).astype("boolean")
    spread_series = board.get("_spread_correct", pd.Series(pd.NA, index=board.index, dtype="boolean")).astype("boolean")
    ml_text, ml_n = _record(ml_series.loc[eligible & ml_series.notna()])
    spread_text, spread_n = _record(spread_series.loc[eligible & spread_series.notna()])
    if spread_n:
        spread_sub = "saved sportsbook picks; no-line/push excluded"
    else:
        spread_text, spread_n = _model_spread_record(board, eligible)
        spread_sub = "frozen model-line results; not ATS wagers" if spread_n else "awaiting graded spread results"

    return [
        ("Games", str(len(board)), "published matchups"),
        ("Strongest pick", strongest, strongest_note),
        ("Average model win", average, "straight-up probability"),
        ("ML record", ml_text, f"{ml_n} graded final" + ("s" if ml_n != 1 else "")),
        ("Spread record", spread_text, spread_sub),
        ("Market coverage", f"{_market_coverage(board)}/{len(board)}", "games with tracked spread or ML"),
    ]
