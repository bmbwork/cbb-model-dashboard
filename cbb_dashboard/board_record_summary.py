"""CFB-style Game Board summary values for CBB.

ML and spread records use only official attached grading. A model-line diagnostic
shown on a card is not allowed to enter the ATS/spread performance record.
"""
from __future__ import annotations

import pandas as pd


def _record(correct: pd.Series) -> tuple[str, int]:
    known = correct.dropna().astype(bool)
    if known.empty:
        return "—", 0
    wins = int(known.sum())
    losses = int(len(known) - wins)
    return f"{wins}-{losses}", int(len(known))


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

    return [
        ("Games", str(len(board)), "published matchups"),
        ("Strongest pick", strongest, strongest_note),
        ("Average model win", average, "straight-up probability"),
        ("ML record", ml_text, f"{ml_n} graded final" + ("s" if ml_n != 1 else "")),
        ("Spread record", spread_text, "saved sportsbook picks; no-line/push excluded" if spread_n else "no saved sportsbook spread grades"),
        ("Market coverage", f"{_market_coverage(board)}/{len(board)}", "games with tracked spread or ML"),
    ]
