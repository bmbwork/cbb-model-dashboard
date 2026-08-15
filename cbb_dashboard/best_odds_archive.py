from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .owlsinsight_odds_provider import OwlsInsightOddsProvider


ARCHIVE_PROVIDER = "owls_insight"
ARCHIVE_MARKETS = ("spread", "moneyline")
VALID_ARCHIVE_ROLES = {"open", "observed", "close"}


def _num(value: Any) -> float:
    number = pd.to_numeric(value, errors="coerce")
    return float(number) if pd.notna(number) else float("nan")


def _stamp(value: Any) -> pd.Timestamp:
    return pd.to_datetime(value, utc=True, errors="coerce")


def archive_event_key(home_team: Any, away_team: Any, commence_time: Any) -> str:
    """Stable event key that is independent of a model slate/Game ID."""
    home = OwlsInsightOddsProvider._canonical_team(home_team)
    away = OwlsInsightOddsProvider._canonical_team(away_team)
    start = _stamp(commence_time)
    start_text = start.isoformat() if pd.notna(start) else str(commence_time or "")
    raw = f"{home}|{away}|{start_text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def _price_rank(value: Any) -> float:
    price = _num(value)
    return price if np.isfinite(price) else -1e12


def _best_spread(candidates: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    usable = [c for c in candidates if np.isfinite(_num(c.get("line")))]
    if not usable:
        return None
    # For a bettor, +4 is better than +3.5 and -3 is better than -3.5.
    # When the point is identical, the higher American price is better.
    return max(usable, key=lambda c: (_num(c.get("line")), _price_rank(c.get("price"))))


def _best_moneyline(candidates: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    usable = [c for c in candidates if np.isfinite(_num(c.get("price")))]
    if not usable:
        return None
    # American odds are monotonic for bettor value: +110 > +100 and -105 > -115.
    return max(usable, key=lambda c: _price_rank(c.get("price")))


def _market_candidates(event: dict[str, Any], market_key: str, team_name: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for book in event.get("bookmakers") or []:
        if not isinstance(book, dict):
            continue
        market = OwlsInsightOddsProvider._market(book, market_key)
        if not market or bool(market.get("suspended")):
            continue
        outcome = OwlsInsightOddsProvider._outcome(market, team_name)
        if not outcome:
            continue
        line = _num(outcome.get("point")) if market_key == "spreads" else float("nan")
        price = _num(outcome.get("price"))
        if market_key == "spreads" and not np.isfinite(line):
            continue
        if market_key == "h2h" and not np.isfinite(price):
            continue
        out.append(
            {
                "line": line,
                "price": price,
                "book_key": str(book.get("key") or "").strip().lower(),
                "book_title": str(book.get("title") or book.get("key") or "Sportsbook").strip(),
            }
        )
    return out


def _combined_book_quotes(home_candidates: list[dict[str, Any]], away_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compact per-book history retained inside one hourly event/market row."""
    merged: dict[str, dict[str, Any]] = {}
    for side, candidates in (("home", home_candidates), ("away", away_candidates)):
        for item in candidates:
            key = str(item.get("book_key") or item.get("book_title") or "unknown")
            row = merged.setdefault(
                key,
                {
                    "book_key": item.get("book_key") or None,
                    "book_title": item.get("book_title") or None,
                    "home_line": None,
                    "home_price": None,
                    "away_line": None,
                    "away_price": None,
                },
            )
            line = _num(item.get("line"))
            price = _num(item.get("price"))
            row[f"{side}_line"] = line if np.isfinite(line) else None
            row[f"{side}_price"] = price if np.isfinite(price) else None
    return [merged[key] for key in sorted(merged)]


def _snapshot_hash(record: dict[str, Any]) -> str:
    # A new scheduled capture should be retained even when the quote is unchanged.
    keys = [
        "archive_event_key",
        "market_type",
        "captured_at_utc",
        "snapshot_role",
        "best_home_line",
        "best_home_price",
        "best_home_book_key",
        "best_away_line",
        "best_away_price",
        "best_away_book_key",
    ]
    payload = {key: record.get(key) for key in keys}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def extract_best_odds_records(
    event: dict[str, Any],
    *,
    captured_at: Any,
    response_timestamp: Any = None,
    snapshot_role: str = "observed",
    capture_trigger: str = "hourly",
) -> list[dict[str, Any]]:
    """Extract best available spread and moneyline for each side across all returned books."""
    role = str(snapshot_role or "observed").strip().lower()
    if role not in VALID_ARCHIVE_ROLES:
        raise ValueError(f"Invalid archive role: {snapshot_role}")

    home = str(event.get("home_team") or "").strip()
    away = str(event.get("away_team") or "").strip()
    start = _stamp(event.get("commence_time"))
    capture = _stamp(captured_at)
    provider_stamp = _stamp(response_timestamp)
    if not home or not away or pd.isna(start) or pd.isna(capture):
        return []

    key = archive_event_key(home, away, start)
    provider_ids = event.get("provider_ids") if isinstance(event.get("provider_ids"), dict) else {}
    provider_event_id = str(event.get("id") or next(iter(provider_ids.values()), ""))
    base = {
        "archive_event_key": key,
        "provider": ARCHIVE_PROVIDER,
        "provider_event_id": provider_event_id or None,
        "home_team": home,
        "away_team": away,
        "commence_time_utc": start.isoformat(),
        "captured_at_utc": capture.isoformat(),
        "provider_timestamp_utc": provider_stamp.isoformat() if pd.notna(provider_stamp) else None,
        "snapshot_role": role,
        "capture_trigger": str(capture_trigger or "hourly"),
    }

    records: list[dict[str, Any]] = []
    market_specs = [("spread", "spreads", _best_spread), ("moneyline", "h2h", _best_moneyline)]
    for market_type, owls_key, selector in market_specs:
        home_candidates = _market_candidates(event, owls_key, home)
        away_candidates = _market_candidates(event, owls_key, away)
        best_home = selector(home_candidates)
        best_away = selector(away_candidates)
        if best_home is None and best_away is None:
            continue
        seen = sorted(
            {
                str(x.get("book_key") or "")
                for x in home_candidates + away_candidates
                if str(x.get("book_key") or "")
            }
        )
        row = dict(base)
        row.update(
            {
                "market_type": market_type,
                "best_home_line": _num((best_home or {}).get("line")) if market_type == "spread" else None,
                "best_home_price": _num((best_home or {}).get("price")) if best_home else None,
                "best_home_book_key": (best_home or {}).get("book_key") or None,
                "best_home_book_title": (best_home or {}).get("book_title") or None,
                "best_away_line": _num((best_away or {}).get("line")) if market_type == "spread" else None,
                "best_away_price": _num((best_away or {}).get("price")) if best_away else None,
                "best_away_book_key": (best_away or {}).get("book_key") or None,
                "best_away_book_title": (best_away or {}).get("book_title") or None,
                "book_count": len(seen),
                "books_seen": seen,
                "book_quotes": _combined_book_quotes(home_candidates, away_candidates),
            }
        )
        # JSON/Supabase should receive null, not NaN.
        for field in ["best_home_line", "best_home_price", "best_away_line", "best_away_price"]:
            value = row.get(field)
            if value is not None and not np.isfinite(_num(value)):
                row[field] = None
        row["raw_snapshot_hash"] = _snapshot_hash(row)
        records.append(row)
    return records


def _match_event(board_row: pd.Series, groups: list[tuple[str, pd.DataFrame]]) -> tuple[pd.DataFrame | None, bool]:
    bh = str(board_row.get("Home Team") or "")
    ba = str(board_row.get("Away Team") or "")
    board_start = _stamp(board_row.get("_start_dt") or board_row.get("Start Time UTC"))
    best: tuple[float, pd.DataFrame, bool] | None = None
    for _, frame in groups:
        first = frame.iloc[0]
        event_start = _stamp(first.get("commence_time_utc"))
        if pd.notna(board_start) and pd.notna(event_start):
            gap_hours = abs((event_start - board_start).total_seconds()) / 3600.0
            if gap_hours > 8.0:
                continue
        eh, ea = str(first.get("home_team") or ""), str(first.get("away_team") or "")
        direct = (
            OwlsInsightOddsProvider._team_score(bh, eh)
            + OwlsInsightOddsProvider._team_score(ba, ea)
        ) / 2.0
        swapped = (
            OwlsInsightOddsProvider._team_score(bh, ea)
            + OwlsInsightOddsProvider._team_score(ba, eh)
        ) / 2.0
        score, is_swapped = (swapped, True) if swapped > direct else (direct, False)
        if pd.notna(board_start) and pd.notna(event_start):
            gap_hours = abs((event_start - board_start).total_seconds()) / 3600.0
            if gap_hours <= 1.0:
                score = min(1.0, score + 0.03)
        if best is None or score > best[0]:
            best = (score, frame, is_swapped)
    if best and best[0] >= 0.78:
        return best[1], best[2]
    return None, False


def _role_row(frame: pd.DataFrame, market: str, role: str) -> pd.Series | None:
    market_rows = frame[frame["market_type"].astype(str).str.lower() == market].copy()
    if market_rows.empty:
        return None
    market_rows["_captured"] = pd.to_datetime(market_rows["captured_at_utc"], utc=True, errors="coerce")
    market_rows = market_rows.sort_values("_captured")
    role_rows = market_rows[market_rows["snapshot_role"].astype(str).str.lower() == role]
    if not role_rows.empty:
        return role_rows.iloc[-1] if role == "close" else role_rows.iloc[0]
    if role == "open":
        return market_rows.iloc[0]
    if role == "current":
        return market_rows.iloc[-1]
    return None


def _copy_side(out: pd.DataFrame, idx: Any, record: pd.Series | None, prefix: str, swapped: bool) -> None:
    if record is None:
        return
    for board_side in ("home", "away"):
        provider_side = "away" if (swapped and board_side == "home") else "home" if (swapped and board_side == "away") else board_side
        for field in ("line", "price", "book_key", "book_title"):
            source = f"best_{provider_side}_{field}"
            if source in record.index:
                out.at[idx, f"_best_{prefix}_{board_side}_{field}"] = record.get(source)
    out.at[idx, f"_best_{prefix}_captured_at_utc"] = record.get("captured_at_utc")
    out.at[idx, f"_best_{prefix}_book_count"] = record.get("book_count")


def attach_best_odds_to_board(board: pd.DataFrame, archive_rows: Iterable[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    """Attach tracked open/current/close best-market quotes to a normalized model board."""
    if board is None or board.empty:
        return board.copy() if isinstance(board, pd.DataFrame) else pd.DataFrame()
    out = board.copy()
    records = archive_rows.copy() if isinstance(archive_rows, pd.DataFrame) else pd.DataFrame(list(archive_rows or []))
    if records.empty or "archive_event_key" not in records.columns:
        return out
    required = {"home_team", "away_team", "commence_time_utc", "market_type", "captured_at_utc", "snapshot_role"}
    if not required.issubset(records.columns):
        return out
    groups = [(str(key), frame.copy()) for key, frame in records.groupby("archive_event_key", dropna=False)]
    for idx, row in out.iterrows():
        frame, swapped = _match_event(row, groups)
        if frame is None or frame.empty:
            continue
        for market in ARCHIVE_MARKETS:
            _copy_side(out, idx, _role_row(frame, market, "open"), f"open_{market}", swapped)
            _copy_side(out, idx, _role_row(frame, market, "current"), f"current_{market}", swapped)
            _copy_side(out, idx, _role_row(frame, market, "close"), f"close_{market}", swapped)
        out.at[idx, "_best_archive_event_key"] = str(frame.iloc[0].get("archive_event_key") or "")
        out.at[idx, "_best_archive_snapshots"] = int(len(frame))
    return out
