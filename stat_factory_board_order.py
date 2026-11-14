"""Display-only ordering shared by the independent Stat Factory dashboards.

Never changes forecast values, model ranks, or publication timestamps.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

CHICAGO = ZoneInfo("America/Chicago")
SORT_TIME = "Game time (earliest first)"
SORT_TOSSUPS = "Toss-up games"
SORT_FAVORITES = "Model top favorites"
SORT_SPREAD_HIGH = "Highest model spread"
SORT_SPREAD_LOW = "Lowest model spread"
SORT_TOTAL_HIGH = "Highest model total"
SORT_TOTAL_LOW = "Lowest model total"
SORT_FAIR_HIGH = "Highest fair odds"
SORT_FAIR_LOW = "Lowest fair odds"
SUPERLATIVE_SORT_OPTIONS = [
    SORT_SPREAD_HIGH, SORT_SPREAD_LOW, SORT_TOTAL_HIGH, SORT_TOTAL_LOW,
    SORT_FAIR_HIGH, SORT_FAIR_LOW,
]
SORT_HELP = (
    "Model spread sorts by size: highest puts the largest projected margin first "
    "(a 10-point spread ahead of 3 points); lowest puts the closest games first. "
    "Model total sorts projected combined points. Fair odds sorts the model pick's "
    "American odds numerically: highest puts -110 ahead of -300; lowest reverses it. "
    "Unavailable values appear last."
)


def next_slate_date(values: Iterable[object], *, now: datetime | date | None = None) -> str | None:
    """Next published game day, with latest historical day as an honest fallback."""
    if now is None:
        today = datetime.now(CHICAGO).date()
    elif isinstance(now, datetime):
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        today = now.astimezone(CHICAGO).date()
    else:
        today = now
    days: set[date] = set()
    for value in values:
        try:
            days.add(date.fromisoformat(str(value)[:10]))
        except (TypeError, ValueError):
            continue
    upcoming = sorted(day for day in days if day >= today)
    return (upcoming[0] if upcoming else max(days)).isoformat() if days else None


def sort_cards(
    frame: pd.DataFrame,
    choice: str,
    *,
    time_column: str,
    probability_column: str | None = None,
    tie_columns: Iterable[str] = (),
) -> pd.DataFrame:
    """Chronological or game-competitiveness ordering; missing values sort last.

    Toss-up means a *game win probability* closest to 50%, not HR probability,
    participation probability, price, or a prop's chance of hitting an arbitrary line.
    """
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    out["_sf_order_time"] = pd.to_datetime(
        out.get(time_column, pd.Series(index=out.index, dtype=object)), utc=True, errors="coerce"
    )
    ties = [name for name in tie_columns if name in out.columns]
    if choice == SORT_TIME:
        columns, ascending = ["_sf_order_time", *ties], [True] * (1 + len(ties))
    elif choice in {SORT_TOSSUPS, SORT_FAVORITES}:
        if not probability_column:
            raise ValueError("Game-win probability is required for toss-up/favorite sorting")
        p = pd.to_numeric(out.get(probability_column, pd.Series(index=out.index, dtype=float)), errors="coerce")
        p = p.where(p.between(0, 1))
        out["_sf_order_probability"] = (p - 0.5).abs()
        columns = ["_sf_order_probability", "_sf_order_time", *ties]
        ascending = [choice == SORT_TOSSUPS, *([True] * (1 + len(ties)))]
    else:
        raise ValueError(f"Unsupported card sort: {choice}")
    return out.sort_values(columns, ascending=ascending, na_position="last", kind="stable").drop(
        columns=["_sf_order_time", "_sf_order_probability"], errors="ignore"
    ).reset_index(drop=True)


def sort_numeric_cards(
    frame: pd.DataFrame,
    values: pd.Series,
    *,
    ascending: bool,
    time_column: str,
    tie_columns: Iterable[str] = (),
) -> pd.DataFrame:
    """Order a display metric, with finite values first and deterministic ties."""
    out = frame.copy()
    metric = pd.to_numeric(values, errors="coerce")
    out["_sf_order_metric"] = metric.where(np.isfinite(metric))
    out["_sf_order_time"] = pd.to_datetime(
        out.get(time_column, pd.Series(index=out.index, dtype=object)), utc=True, errors="coerce"
    )
    ties = [name for name in tie_columns if name in out.columns]
    return out.sort_values(
        ["_sf_order_metric", "_sf_order_time", *ties],
        ascending=[ascending, *([True] * (1 + len(ties)))],
        na_position="last", kind="stable",
    ).drop(columns=["_sf_order_metric", "_sf_order_time"]).reset_index(drop=True)
