from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Iterable

import numpy as np
import pandas as pd


MARKET_TYPES = {"spread", "moneyline", "total"}
MANUAL_REQUIRED = {"Slate Date", "Game ID", "Snapshot Time UTC", "Market Type", "Provider"}


class MarketDataError(ValueError):
    pass


def _num(value: Any) -> float:
    out = pd.to_numeric(value, errors="coerce")
    return float(out) if pd.notna(out) else float("nan")


def _pct(value: Any) -> float:
    x = _num(value)
    if not np.isfinite(x):
        return float("nan")
    if abs(x) <= 1.000001:
        x *= 100.0
    return float(np.clip(x, 0.0, 100.0))


def normalize_team_name(value: Any) -> str:
    text = str(value or "").lower().strip()
    text = text.replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    stop = {
        "university", "college", "men", "mens", "basketball",
        "wildcats", "tigers", "bulldogs", "eagles", "bears", "panthers",
        "cardinals", "cougars", "hawks", "red", "blue", "golden",
    }
    parts = [p for p in text.split() if p not in stop]
    return " ".join(parts)


def _snapshot_hash(payload: dict[str, Any]) -> str:
    clean = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


def _safe_iso(value: Any) -> str:
    stamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(stamp):
        return ""
    return stamp.isoformat()


def _first_number(row: pd.Series, names: Iterable[str]) -> float:
    for name in names:
        if name in row.index:
            x = _num(row.get(name))
            if np.isfinite(x):
                return x
    return float("nan")


def normalize_market_import(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize a provider/manual market-snapshot import.

    One row represents one market (spread, moneyline, or total) for one game at
    one observation time. Percent fields may be supplied as 0-1 or 0-100.
    """
    if frame is None or frame.empty:
        raise MarketDataError("Market snapshot file is empty.")
    out = frame.copy()
    out.columns = [str(c).strip() for c in out.columns]
    missing = [c for c in MANUAL_REQUIRED if c not in out.columns]
    if missing:
        raise MarketDataError("Missing market snapshot columns: " + ", ".join(sorted(missing)))

    out["Slate Date"] = pd.to_datetime(out["Slate Date"], errors="coerce").dt.date.astype("string")
    out["Snapshot Time UTC"] = pd.to_datetime(out["Snapshot Time UTC"], errors="coerce", utc=True)
    if out["Snapshot Time UTC"].isna().any():
        raise MarketDataError("Every market snapshot needs a valid Snapshot Time UTC.")
    out["Market Type"] = out["Market Type"].astype(str).str.strip().str.lower()
    bad_market = sorted(set(out.loc[~out["Market Type"].isin(MARKET_TYPES), "Market Type"].tolist()))
    if bad_market:
        raise MarketDataError(f"Unsupported Market Type value(s): {bad_market}. Use spread, moneyline, or total.")
    out["Game ID"] = out["Game ID"].astype(str).str.strip()
    if out["Game ID"].eq("").any():
        raise MarketDataError("Every market snapshot needs a Game ID matching the published CBB board.")
    out["Provider"] = out["Provider"].fillna("manual").astype(str).str.strip()
    out["Provider Game ID"] = out.get("Provider Game ID", pd.Series("", index=out.index)).fillna("").astype(str)
    out["Source Label"] = out.get("Source Label", out["Provider"]).fillna(out["Provider"]).astype(str)
    out["Snapshot Role"] = out.get("Snapshot Role", pd.Series("observed", index=out.index)).fillna("observed").astype(str).str.lower()
    out["Sportsbook Scope"] = out.get("Sportsbook Scope", pd.Series("", index=out.index)).fillna("").astype(str)
    out["Activity Level"] = out.get("Activity Level", pd.Series("", index=out.index)).fillna("").astype(str)
    out["Provider Signals"] = out.get("Provider Signals", pd.Series("", index=out.index)).fillna("").astype(str)
    out["Book Agreement"] = out.get("Book Agreement", pd.Series("", index=out.index)).fillna("").astype(str)
    for col in ["Ticket Leader", "Money Leader", "Sharp Side", "Sharp Strength", "Sharp Signal", "Sharp Read", "Sharp Rule Version", "Capture Trigger"]:
        if col not in out.columns:
            out[col] = ""
        out[col] = out[col].fillna("").astype(str)

    pct_cols = [
        "Home Ticket %", "Away Ticket %", "Home Money %", "Away Money %",
        "Over Ticket %", "Under Ticket %", "Over Money %", "Under Money %",
    ]
    for col in pct_cols:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = out[col].map(_pct)

    numeric_cols = [
        "Home Line", "Away Line", "Total Line", "Opening Home Line", "Opening Away Line",
        "Opening Total", "Home Price", "Away Price", "Over Price", "Under Price",
        "Minutes To Tip", "Ticket Count", "Book Count", "Home Spread Min", "Home Spread Max", "Book Spread Range", "Sharp Gap Pts",
    ]
    for col in numeric_cols:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")

    # Some optional betting-split providers expose a tracked ticket count.
    # Convert that sample-size signal into a simple reliability label only when
    # the provider/import did not supply its own activity label.
    blank_activity = out["Activity Level"].astype(str).str.strip().eq("")
    tc = pd.to_numeric(out["Ticket Count"], errors="coerce")
    inferred_activity = pd.Series("", index=out.index, dtype="object")
    inferred_activity.loc[tc.notna() & (tc < 250)] = "low"
    inferred_activity.loc[tc.notna() & (tc >= 250) & (tc < 1000)] = "moderate"
    inferred_activity.loc[tc.notna() & (tc >= 1000) & (tc < 2500)] = "high"
    inferred_activity.loc[tc.notna() & (tc >= 2500)] = "very high"
    out.loc[blank_activity, "Activity Level"] = inferred_activity.loc[blank_activity]

    # Fill complementary percentages when exactly one side was supplied.
    for a, b in [
        ("Home Ticket %", "Away Ticket %"), ("Home Money %", "Away Money %"),
        ("Over Ticket %", "Under Ticket %"), ("Over Money %", "Under Money %"),
    ]:
        out[b] = out[b].where(out[b].notna(), 100.0 - out[a])
        out[a] = out[a].where(out[a].notna(), 100.0 - out[b])

    if "Raw Snapshot Hash" not in out.columns:
        hashes = []
        for _, row in out.iterrows():
            payload = {
                "slate_date": row["Slate Date"], "game_id": row["Game ID"],
                "provider": row["Provider"], "provider_game_id": row["Provider Game ID"],
                "market": row["Market Type"], "role": row["Snapshot Role"],
                "snapshot": _safe_iso(row["Snapshot Time UTC"]),
                "home_ticket": row["Home Ticket %"], "away_ticket": row["Away Ticket %"],
                "home_money": row["Home Money %"], "away_money": row["Away Money %"],
                "over_ticket": row["Over Ticket %"], "under_ticket": row["Under Ticket %"],
                "over_money": row["Over Money %"], "under_money": row["Under Money %"],
                "home_line": row["Home Line"], "away_line": row["Away Line"],
                "total": row["Total Line"], "opening_home": row["Opening Home Line"],
                "opening_away": row["Opening Away Line"], "opening_total": row["Opening Total"],
                "home_price": row["Home Price"], "away_price": row["Away Price"],
                "over_price": row["Over Price"], "under_price": row["Under Price"],
                "ticket_count": row["Ticket Count"], "provider_signals": row["Provider Signals"],
                "book_count": row["Book Count"], "book_spread_range": row["Book Spread Range"],
                "book_agreement": row["Book Agreement"],
            }
            hashes.append(_snapshot_hash(payload))
        out["Raw Snapshot Hash"] = hashes

    return out


def market_records(frame: pd.DataFrame, actor: str = "") -> list[dict[str, Any]]:
    normalized = normalize_market_import(frame)
    records: list[dict[str, Any]] = []
    for _, row in normalized.iterrows():
        record = {
            "slate_date": str(row["Slate Date"]),
            "game_id": str(row["Game ID"]),
            "provider": str(row["Provider"]),
            "provider_game_id": str(row["Provider Game ID"] or ""),
            "market_type": str(row["Market Type"]),
            "snapshot_time_utc": _safe_iso(row["Snapshot Time UTC"]),
            "snapshot_role": str(row["Snapshot Role"] or "observed"),
            "minutes_to_tip": None if pd.isna(row["Minutes To Tip"]) else float(row["Minutes To Tip"]),
            "home_ticket_pct": None if pd.isna(row["Home Ticket %"]) else float(row["Home Ticket %"]),
            "away_ticket_pct": None if pd.isna(row["Away Ticket %"]) else float(row["Away Ticket %"]),
            "home_money_pct": None if pd.isna(row["Home Money %"]) else float(row["Home Money %"]),
            "away_money_pct": None if pd.isna(row["Away Money %"]) else float(row["Away Money %"]),
            "over_ticket_pct": None if pd.isna(row["Over Ticket %"]) else float(row["Over Ticket %"]),
            "under_ticket_pct": None if pd.isna(row["Under Ticket %"]) else float(row["Under Ticket %"]),
            "over_money_pct": None if pd.isna(row["Over Money %"]) else float(row["Over Money %"]),
            "under_money_pct": None if pd.isna(row["Under Money %"]) else float(row["Under Money %"]),
            "home_line": None if pd.isna(row["Home Line"]) else float(row["Home Line"]),
            "away_line": None if pd.isna(row["Away Line"]) else float(row["Away Line"]),
            "total_line": None if pd.isna(row["Total Line"]) else float(row["Total Line"]),
            "opening_home_line": None if pd.isna(row["Opening Home Line"]) else float(row["Opening Home Line"]),
            "opening_away_line": None if pd.isna(row["Opening Away Line"]) else float(row["Opening Away Line"]),
            "opening_total": None if pd.isna(row["Opening Total"]) else float(row["Opening Total"]),
            "home_price": None if pd.isna(row["Home Price"]) else float(row["Home Price"]),
            "away_price": None if pd.isna(row["Away Price"]) else float(row["Away Price"]),
            "over_price": None if pd.isna(row["Over Price"]) else float(row["Over Price"]),
            "under_price": None if pd.isna(row["Under Price"]) else float(row["Under Price"]),
            "source_label": str(row["Source Label"] or row["Provider"]),
            "sportsbook_scope": str(row["Sportsbook Scope"] or ""),
            "activity_level": str(row["Activity Level"] or ""),
            "ticket_count": None if pd.isna(row["Ticket Count"]) else int(row["Ticket Count"]),
            "provider_signals": str(row["Provider Signals"] or ""),
            "book_count": None if pd.isna(row["Book Count"]) else int(row["Book Count"]),
            "home_spread_min": None if pd.isna(row["Home Spread Min"]) else float(row["Home Spread Min"]),
            "home_spread_max": None if pd.isna(row["Home Spread Max"]) else float(row["Home Spread Max"]),
            "book_spread_range": None if pd.isna(row["Book Spread Range"]) else float(row["Book Spread Range"]),
            "book_agreement": str(row["Book Agreement"] or ""),
            "ticket_leader": str(row.get("Ticket Leader") or ""),
            "money_leader": str(row.get("Money Leader") or ""),
            "sharp_side": str(row.get("Sharp Side") or ""),
            "sharp_gap_pts": None if pd.isna(pd.to_numeric(row.get("Sharp Gap Pts"), errors="coerce")) else float(pd.to_numeric(row.get("Sharp Gap Pts"), errors="coerce")),
            "sharp_strength": str(row.get("Sharp Strength") or ""),
            "sharp_signal": str(row.get("Sharp Signal") or "none"),
            "sharp_read": str(row.get("Sharp Read") or ""),
            "sharp_rule_version": str(row.get("Sharp Rule Version") or "ticket_handle_gap_v1"),
            "capture_trigger": str(row.get("Capture Trigger") or ""),
            "raw_snapshot_hash": str(row["Raw Snapshot Hash"]),
            "published_by": actor or None,
        }
        records.append(record)
    return records


def snapshots_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    out = pd.DataFrame(records)
    rename = {
        "slate_date":"Slate Date", "game_id":"Game ID", "provider":"Provider",
        "provider_game_id":"Provider Game ID", "market_type":"Market Type",
        "snapshot_time_utc":"Snapshot Time UTC", "snapshot_role":"Snapshot Role",
        "minutes_to_tip":"Minutes To Tip", "home_ticket_pct":"Home Ticket %",
        "away_ticket_pct":"Away Ticket %", "home_money_pct":"Home Money %",
        "away_money_pct":"Away Money %", "over_ticket_pct":"Over Ticket %",
        "under_ticket_pct":"Under Ticket %", "over_money_pct":"Over Money %",
        "under_money_pct":"Under Money %", "home_line":"Home Line", "away_line":"Away Line",
        "total_line":"Total Line", "opening_home_line":"Opening Home Line",
        "opening_away_line":"Opening Away Line", "opening_total":"Opening Total",
        "home_price":"Home Price", "away_price":"Away Price", "over_price":"Over Price",
        "under_price":"Under Price", "source_label":"Source Label",
        "sportsbook_scope":"Sportsbook Scope", "activity_level":"Activity Level",
        "ticket_count":"Ticket Count", "provider_signals":"Provider Signals",
        "book_count":"Book Count", "home_spread_min":"Home Spread Min", "home_spread_max":"Home Spread Max",
        "book_spread_range":"Book Spread Range", "book_agreement":"Book Agreement",
        "ticket_leader":"Ticket Leader", "money_leader":"Money Leader",
        "sharp_side":"Sharp Side", "sharp_gap_pts":"Sharp Gap Pts",
        "sharp_strength":"Sharp Strength", "sharp_signal":"Sharp Signal",
        "sharp_read":"Sharp Read", "sharp_rule_version":"Sharp Rule Version",
        "capture_trigger":"Capture Trigger", "raw_snapshot_hash":"Raw Snapshot Hash",
    }
    out = out.rename(columns=rename)
    return normalize_market_import(out)


def normalize_context_import(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        raise MarketDataError("Game-context file is empty.")
    out = frame.copy()
    out.columns = [str(c).strip() for c in out.columns]
    required = ["Slate Date", "Game ID"]
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise MarketDataError("Missing game-context columns: " + ", ".join(missing))
    out["Slate Date"] = pd.to_datetime(out["Slate Date"], errors="coerce").dt.date.astype("string")
    out["Game ID"] = out["Game ID"].astype(str).str.strip()
    for col in ["Home Rank", "Away Rank"]:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in ["Conference Game", "Saturday", "Prime Time", "Neutral Site"]:
        if col not in out.columns:
            out[col] = False
        out[col] = out[col].map(lambda x: str(x).strip().lower() in {"true","1","yes","y"} if not isinstance(x,(bool,np.bool_)) else bool(x))
    for col in ["Home Conference", "Away Conference", "Provider", "Provider Game ID", "Context Source", "Local Start",
                "Betting Public Side", "Betting Money Side", "Betting Signal", "Betting Label",
                "Betting Note", "Betting Source", "Betting Books", "Betting Updated At",
                "Betting Sharp Side", "Betting Sharp Signal", "Betting Sharp Confidence",
                "Betting Sharp Note", "Betting Sharp Books"]:
        if col not in out.columns:
            out[col] = ""
        out[col] = out[col].fillna("").astype(str)
    return out


def context_records(frame: pd.DataFrame, actor: str = "") -> list[dict[str, Any]]:
    out = normalize_context_import(frame)
    records = []
    for _, row in out.iterrows():
        records.append({
            "slate_date": str(row["Slate Date"]),
            "game_id": str(row["Game ID"]),
            "provider": str(row["Provider"] or "manual"),
            "provider_game_id": str(row["Provider Game ID"] or ""),
            "home_rank": None if pd.isna(row["Home Rank"]) else int(row["Home Rank"]),
            "away_rank": None if pd.isna(row["Away Rank"]) else int(row["Away Rank"]),
            "home_conference": str(row["Home Conference"] or ""),
            "away_conference": str(row["Away Conference"] or ""),
            "conference_game": bool(row["Conference Game"]),
            "saturday": bool(row["Saturday"]),
            "prime_time": bool(row["Prime Time"]),
            "neutral_site": bool(row["Neutral Site"]),
            "local_start": str(row["Local Start"] or ""),
            "context_source": str(row["Context Source"] or row["Provider"] or "manual"),
            "betting_public_side": str(row.get("Betting Public Side") or "") or None,
            "betting_money_side": str(row.get("Betting Money Side") or "") or None,
            "betting_signal": str(row.get("Betting Signal") or "") or None,
            "betting_label": str(row.get("Betting Label") or "") or None,
            "betting_note": str(row.get("Betting Note") or "") or None,
            "betting_source": str(row.get("Betting Source") or "") or None,
            "betting_books": str(row.get("Betting Books") or "") or None,
            "betting_updated_at": str(row.get("Betting Updated At") or "") or None,
            "betting_sharp_side": str(row.get("Betting Sharp Side") or "") or None,
            "betting_sharp_signal": str(row.get("Betting Sharp Signal") or "") or None,
            "betting_sharp_confidence": str(row.get("Betting Sharp Confidence") or "") or None,
            "betting_sharp_note": str(row.get("Betting Sharp Note") or "") or None,
            "betting_sharp_books": str(row.get("Betting Sharp Books") or "") or None,
            "published_by": actor or None,
        })
    return records


def context_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    out = pd.DataFrame(records).rename(columns={
        "slate_date":"Slate Date", "game_id":"Game ID", "provider":"Provider",
        "provider_game_id":"Provider Game ID", "home_rank":"Home Rank", "away_rank":"Away Rank",
        "home_conference":"Home Conference", "away_conference":"Away Conference",
        "conference_game":"Conference Game", "saturday":"Saturday", "prime_time":"Prime Time",
        "neutral_site":"Neutral Site", "local_start":"Local Start", "context_source":"Context Source",
        "betting_public_side":"Betting Public Side", "betting_money_side":"Betting Money Side",
        "betting_signal":"Betting Signal", "betting_label":"Betting Label", "betting_note":"Betting Note",
        "betting_source":"Betting Source", "betting_books":"Betting Books", "betting_updated_at":"Betting Updated At",
        "betting_sharp_side":"Betting Sharp Side", "betting_sharp_signal":"Betting Sharp Signal",
        "betting_sharp_confidence":"Betting Sharp Confidence", "betting_sharp_note":"Betting Sharp Note",
        "betting_sharp_books":"Betting Sharp Books",
    })
    return normalize_context_import(out)


@dataclass(frozen=True)
class GameMarketState:
    game_id: str
    provider: str = ""
    source_label: str = ""
    latest_snapshot_utc: str = ""
    split_provider: str = ""
    split_source_label: str = ""
    split_latest_snapshot_utc: str = ""
    home_ticket_pct: float = np.nan
    away_ticket_pct: float = np.nan
    home_money_pct: float = np.nan
    away_money_pct: float = np.nan
    opening_home_spread: float = np.nan
    current_home_spread: float = np.nan
    decision_home_spread: float = np.nan
    closing_home_spread: float = np.nan
    moneyline_home_ticket_pct: float = np.nan
    moneyline_home_money_pct: float = np.nan
    total_over_ticket_pct: float = np.nan
    total_over_money_pct: float = np.nan
    total_line: float = np.nan
    activity_level: str = ""
    ticket_count: float = np.nan
    provider_signals: str = ""
    book_count: float = np.nan
    book_spread_range: float = np.nan
    book_agreement: str = ""


def _model_run_time(row: pd.Series) -> pd.Timestamp | None:
    for col in ["Model Run At UTC", "Prediction Timestamp UTC", "Run Timestamp UTC"]:
        if col in row.index:
            ts = pd.to_datetime(row.get(col), utc=True, errors="coerce")
            if pd.notna(ts):
                return ts
    return None


def _start_time(row: pd.Series) -> pd.Timestamp | None:
    ts = row.get("_start_dt") if "_start_dt" in row.index else row.get("Start Time UTC")
    ts = pd.to_datetime(ts, utc=True, errors="coerce")
    return ts if pd.notna(ts) else None


def _role_row(group: pd.DataFrame, role: str) -> pd.Series | None:
    hit = group[group["Snapshot Role"].astype(str).str.lower().eq(role)]
    if hit.empty:
        return None
    return hit.sort_values("Snapshot Time UTC").iloc[-1]


def _decision_row(group: pd.DataFrame, model_time: pd.Timestamp | None, start: pd.Timestamp | None) -> pd.Series | None:
    # Data-provenance firewall: only an explicitly tagged decision snapshot can
    # become an ATS grading line. An ordinary observed snapshot is never silently
    # promoted to a decision/taken line.
    explicit = _role_row(group, "decision")
    if explicit is None:
        return None
    if start is not None and pd.to_datetime(explicit.get("Snapshot Time UTC"), utc=True, errors="coerce") >= start:
        return None
    return explicit


def _closing_row(group: pd.DataFrame, start: pd.Timestamp | None) -> pd.Series | None:
    # Closing lines are also explicit-only. A late observed snapshot remains an
    # observation unless an admin intentionally labels it close.
    explicit = _role_row(group, "close")
    if explicit is None:
        return None
    if start is not None and pd.to_datetime(explicit.get("Snapshot Time UTC"), utc=True, errors="coerce") >= start:
        return None
    return explicit


def summarize_game_market(row: pd.Series, snapshots: pd.DataFrame) -> GameMarketState:
    gid = str(row.get("Game ID") or "")
    if snapshots is None or snapshots.empty:
        return GameMarketState(game_id=gid)
    snap = snapshots[snapshots["Game ID"].astype(str).eq(gid)].copy()
    if snap.empty:
        return GameMarketState(game_id=gid)
    snap["Snapshot Time UTC"] = pd.to_datetime(snap["Snapshot Time UTC"], utc=True, errors="coerce")
    snap = snap[snap["Snapshot Time UTC"].notna()]
    if snap.empty:
        return GameMarketState(game_id=gid)
    spread = snap[snap["Market Type"].eq("spread")].copy()
    ml = snap[snap["Market Type"].eq("moneyline")].copy()
    total = snap[snap["Market Type"].eq("total")].copy()
    model_time, start = _model_run_time(row), _start_time(row)

    # Pregame-only display state. Post-start observations remain in storage for
    # audit but never affect cards, ATS, CLV, or research features.
    if start is not None:
        spread_display = spread[spread["Snapshot Time UTC"] < start].copy()
        ml_display = ml[ml["Snapshot Time UTC"] < start].copy()
        total_display = total[total["Snapshot Time UTC"] < start].copy()
    else:
        spread_display, ml_display, total_display = spread, ml, total

    def latest_with(group: pd.DataFrame, cols: list[str]) -> pd.Series | None:
        if group.empty:
            return None
        mask = pd.Series(False, index=group.index)
        for col in cols:
            if col in group.columns:
                mask = mask | pd.to_numeric(group[col], errors="coerce").notna()
        hit = group.loc[mask].copy()
        if hit.empty:
            return None
        return hit.sort_values("Snapshot Time UTC").iloc[-1]

    line_spread = latest_with(spread_display, ["Home Line", "Away Line"])
    split_spread = latest_with(spread_display, ["Home Ticket %", "Away Ticket %", "Home Money %", "Away Money %"])
    split_ml = latest_with(ml_display, ["Home Ticket %", "Away Ticket %", "Home Money %", "Away Money %"])
    line_total = latest_with(total_display, ["Total Line"])
    split_total = latest_with(total_display, ["Over Ticket %", "Under Ticket %", "Over Money %", "Under Money %"])

    decision = _decision_row(spread, model_time, start) if not spread.empty else None
    closing = _closing_row(spread, start) if not spread.empty else None
    open_explicit = _role_row(spread, "open") if not spread.empty else None
    first_line = None
    if not spread_display.empty:
        line_candidates = spread_display[pd.to_numeric(spread_display.get("Home Line"), errors="coerce").notna()].copy()
        if not line_candidates.empty:
            first_line = line_candidates.sort_values("Snapshot Time UTC").iloc[0]
    opening = open_explicit if open_explicit is not None else first_line

    def val(r: pd.Series | None, col: str) -> float:
        return _num(r.get(col)) if r is not None else float("nan")

    open_line = val(opening, "Opening Home Line")
    if not np.isfinite(open_line):
        open_line = val(opening, "Home Line")

    line_source_row = line_spread if line_spread is not None else (line_total if line_total is not None else opening)
    split_source_row = split_spread if split_spread is not None else (split_ml if split_ml is not None else split_total)
    provider = str(line_source_row.get("Provider") or "") if line_source_row is not None else ""
    source = str(line_source_row.get("Source Label") or provider) if line_source_row is not None else ""
    split_provider = str(split_source_row.get("Provider") or "") if split_source_row is not None else ""
    split_source = str(split_source_row.get("Source Label") or split_provider) if split_source_row is not None else ""

    return GameMarketState(
        game_id=gid,
        provider=provider,
        source_label=source,
        latest_snapshot_utc=_safe_iso(line_source_row.get("Snapshot Time UTC")) if line_source_row is not None else "",
        split_provider=split_provider,
        split_source_label=split_source,
        split_latest_snapshot_utc=_safe_iso(split_source_row.get("Snapshot Time UTC")) if split_source_row is not None else "",
        home_ticket_pct=val(split_spread, "Home Ticket %"),
        away_ticket_pct=val(split_spread, "Away Ticket %"),
        home_money_pct=val(split_spread, "Home Money %"),
        away_money_pct=val(split_spread, "Away Money %"),
        opening_home_spread=open_line,
        current_home_spread=val(line_spread, "Home Line"),
        decision_home_spread=val(decision, "Home Line"),
        closing_home_spread=val(closing, "Home Line"),
        moneyline_home_ticket_pct=val(split_ml, "Home Ticket %"),
        moneyline_home_money_pct=val(split_ml, "Home Money %"),
        total_over_ticket_pct=val(split_total, "Over Ticket %"),
        total_over_money_pct=val(split_total, "Over Money %"),
        total_line=val(line_total, "Total Line"),
        activity_level=str(split_source_row.get("Activity Level") or "") if split_source_row is not None else "",
        ticket_count=val(split_source_row, "Ticket Count"),
        provider_signals=str(split_source_row.get("Provider Signals") or "") if split_source_row is not None else "",
        book_count=val(line_spread, "Book Count"),
        book_spread_range=val(line_spread, "Book Spread Range"),
        book_agreement=str(line_spread.get("Book Agreement") or "") if line_spread is not None else "",
    )


def _leader(home: str, away: str, hp: float, ap: float) -> tuple[str, float]:
    if not (np.isfinite(hp) or np.isfinite(ap)):
        return "", float("nan")
    if not np.isfinite(ap) and np.isfinite(hp):
        ap = 100.0 - hp
    if not np.isfinite(hp) and np.isfinite(ap):
        hp = 100.0 - ap
    return (home, hp) if hp >= ap else (away, ap)


def market_features(row: pd.Series) -> dict[str, Any]:
    home, away = str(row.get("Home Team") or "Home"), str(row.get("Away Team") or "Away")
    ht, at = _num(row.get("_market_home_ticket_pct")), _num(row.get("_market_away_ticket_pct"))
    hm, am = _num(row.get("_market_home_money_pct")), _num(row.get("_market_away_money_pct"))
    ticket_team, ticket_pct = _leader(home, away, ht, at)
    money_team, money_pct = _leader(home, away, hm, am)
    opening = _num(row.get("_market_opening_home_spread"))
    current = _num(row.get("_market_current_home_spread"))
    move = opening - current if np.isfinite(opening) and np.isfinite(current) else float("nan")
    move_team = home if np.isfinite(move) and move > 0.05 else (away if np.isfinite(move) and move < -0.05 else "")
    move_pts = abs(move) if np.isfinite(move) else float("nan")
    public_heavy = np.isfinite(ticket_pct) and ticket_pct >= 65
    money_gap_home = hm - ht if np.isfinite(hm) and np.isfinite(ht) else float("nan")
    reverse = bool(public_heavy and move_team and ticket_team and move_team != ticket_team and np.isfinite(move_pts) and move_pts >= 0.5)
    model_pick = str(row.get("Model Pick") or "")
    agreements = [x for x in [ticket_team, money_team, move_team] if x]
    model_agreement = sum(x == model_pick for x in agreements)
    model_conflict = sum(x != model_pick for x in agreements)
    return {
        "ticket_team": ticket_team, "ticket_pct": ticket_pct,
        "money_team": money_team, "money_pct": money_pct,
        "money_ticket_gap_home": money_gap_home,
        "line_move_team": move_team, "line_move_points": move_pts,
        "reverse_line_movement": reverse,
        "public_heavy": public_heavy,
        "model_market_agreement_count": model_agreement,
        "model_market_conflict_count": model_conflict,
    }


def attach_market_to_board(board: pd.DataFrame, snapshots: pd.DataFrame, context: pd.DataFrame | None = None) -> pd.DataFrame:
    out = board.copy()
    state_rows = []
    for _, row in out.iterrows():
        s = summarize_game_market(row, snapshots)
        state_rows.append({
            "Game ID": str(row.get("Game ID")),
            "_market_provider": s.provider,
            "_market_source_label": s.source_label,
            "_market_latest_snapshot_utc": s.latest_snapshot_utc,
            "_market_split_provider": s.split_provider,
            "_market_split_source_label": s.split_source_label,
            "_market_split_latest_snapshot_utc": s.split_latest_snapshot_utc,
            "_market_home_ticket_pct": s.home_ticket_pct,
            "_market_away_ticket_pct": s.away_ticket_pct,
            "_market_home_money_pct": s.home_money_pct,
            "_market_away_money_pct": s.away_money_pct,
            "_market_opening_home_spread": s.opening_home_spread,
            "_market_current_home_spread": s.current_home_spread,
            "_market_decision_home_spread": s.decision_home_spread,
            "_market_closing_home_spread": s.closing_home_spread,
            "_market_ml_home_ticket_pct": s.moneyline_home_ticket_pct,
            "_market_ml_home_money_pct": s.moneyline_home_money_pct,
            "_market_total_over_ticket_pct": s.total_over_ticket_pct,
            "_market_total_over_money_pct": s.total_over_money_pct,
            "_market_total_line": s.total_line,
            "_market_activity_level": s.activity_level,
            "_market_ticket_count": s.ticket_count,
            "_market_provider_signals": s.provider_signals,
            "_market_book_count": s.book_count,
            "_market_book_spread_range": s.book_spread_range,
            "_market_book_agreement": s.book_agreement,
        })
    state = pd.DataFrame(state_rows)
    out["__gid"] = out["Game ID"].astype(str)
    state["__gid"] = state["Game ID"].astype(str)
    out = out.merge(state.drop(columns=["Game ID"]), on="__gid", how="left", validate="one_to_one").drop(columns=["__gid"])

    # Use market snapshots as the ATS/CLV source only when the board/grader did not
    # already publish an explicit pregame line. This keeps grading provenance clear.
    decision = pd.to_numeric(out.get("_market_decision_home_spread", pd.Series(np.nan, index=out.index)), errors="coerce")
    existing_decision = pd.to_numeric(out.get("_market_home_spread", pd.Series(np.nan, index=out.index)), errors="coerce")
    use_decision = existing_decision.isna() & decision.notna()
    out.loc[use_decision, "_market_home_spread"] = decision.loc[use_decision]
    out.loc[use_decision, "_spread_source"] = out.loc[use_decision, "_market_source_label"].fillna("market snapshot") + " · decision-time spread"
    close = pd.to_numeric(out.get("_market_closing_home_spread", pd.Series(np.nan, index=out.index)), errors="coerce")
    existing_close = pd.to_numeric(out.get("_closing_home_spread", pd.Series(np.nan, index=out.index)), errors="coerce")
    use_close = existing_close.isna() & close.notna()
    out.loc[use_close, "_closing_home_spread"] = close.loc[use_close]
    out.loc[use_close, "_closing_source"] = out.loc[use_close, "_market_source_label"].fillna("market snapshot") + " · closing spread"

    # If a game is graded and no explicit ATS result was supplied, grade against
    # the contemporaneous decision line now available from market snapshots.
    if "_grade_eligible" in out.columns and "_spread_correct" in out.columns:
        actual_home_margin = pd.to_numeric(out.get("Actual Home Margin", pd.Series(np.nan, index=out.index)), errors="coerce")
        # attach_grading does not keep Actual Home Margin, so reconstruct it from final scores when needed.
        if actual_home_margin.isna().all():
            actual_home_margin = pd.to_numeric(out.get("_final_home"), errors="coerce") - pd.to_numeric(out.get("_final_away"), errors="coerce")
        home_line = pd.to_numeric(out.get("_market_home_spread"), errors="coerce")
        ats_margin = actual_home_margin + home_line
        missing = out["_spread_correct"].isna() & out["_grade_eligible"].fillna(False).astype(bool) & ats_margin.notna() & ats_margin.ne(0)
        pick_home = out["Model Pick"].astype(str).eq(out["Home Team"].astype(str))
        pick_away = out["Model Pick"].astype(str).eq(out["Away Team"].astype(str))
        out.loc[missing & pick_home, "_spread_correct"] = ats_margin.loc[missing & pick_home] > 0
        out.loc[missing & pick_away, "_spread_correct"] = ats_margin.loc[missing & pick_away] < 0
        out["_spread_correct"] = out["_spread_correct"].astype("boolean")

    if context is not None and not context.empty:
        ctx = normalize_context_import(context)
        ctx["__gid"] = ctx["Game ID"].astype(str)
        keep = [c for c in ["__gid", "Home Rank", "Away Rank", "Home Conference", "Away Conference", "Conference Game", "Saturday", "Prime Time", "Local Start", "Context Source", "Provider Game ID",
                            "Betting Public Side", "Betting Money Side", "Betting Signal", "Betting Label", "Betting Note", "Betting Source", "Betting Books", "Betting Updated At",
                            "Betting Sharp Side", "Betting Sharp Signal", "Betting Sharp Confidence", "Betting Sharp Note", "Betting Sharp Books"] if c in ctx.columns]
        ctx = ctx[keep].drop_duplicates("__gid", keep="last")
        out["__gid"] = out["Game ID"].astype(str)
        out = out.merge(ctx, on="__gid", how="left", suffixes=("", "_context")).drop(columns=["__gid"])
    return out


def context_flags(row: pd.Series) -> dict[str, Any]:
    hr = _num(row.get("Home Rank"))
    ar = _num(row.get("Away Rank"))
    ranked_vs_ranked = np.isfinite(hr) and hr <= 25 and np.isfinite(ar) and ar <= 25
    conference_game = bool(row.get("Conference Game", False))
    saturday = bool(row.get("Saturday", False))
    prime = bool(row.get("Prime Time", False))
    spotlight = ranked_vs_ranked and conference_game and saturday and prime
    return {
        "ranked_vs_ranked": ranked_vs_ranked,
        "conference_game": conference_game,
        "saturday": saturday,
        "prime_time": prime,
        "spotlight": spotlight,
        "home_rank": int(hr) if np.isfinite(hr) else None,
        "away_rank": int(ar) if np.isfinite(ar) else None,
    }


def market_research_frame(board: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in board.iterrows():
        f = market_features(row)
        c = context_flags(row)
        rows.append({
            "Slate Date": row.get("Target Date"), "Game ID": row.get("Game ID"),
            "Away Team": row.get("Away Team"), "Home Team": row.get("Home Team"),
            "Model Pick": row.get("Model Pick"), "Model Win Probability": row.get("Win Probability"),
            "Model Spread": row.get("Fair Spread"), "Start Time UTC": row.get("Start Time UTC"),
            "Local Start": row.get("Local Start"), "Neutral Site": row.get("Neutral Site"),
            "Home Rank": c["home_rank"], "Away Rank": c["away_rank"],
            "Ranked vs Ranked": c["ranked_vs_ranked"], "Conference Game": c["conference_game"],
            "Saturday": c["saturday"], "Prime Time": c["prime_time"], "Market Spotlight": c["spotlight"],
            "Ticket Leader": f["ticket_team"], "Ticket Leader %": f["ticket_pct"],
            "Money Leader": f["money_team"], "Money Leader %": f["money_pct"],
            "Home Money-Ticket Gap": f["money_ticket_gap_home"],
            "Line Move Toward": f["line_move_team"], "Line Move Points": f["line_move_points"],
            "Reverse Line Movement": f["reverse_line_movement"],
            "Opening Home Spread": row.get("_market_opening_home_spread"),
            "Current Home Spread": row.get("_market_current_home_spread"),
            "Decision Home Spread": row.get("_market_decision_home_spread"),
            "Closing Home Spread": row.get("_market_closing_home_spread"),
            "Decision Line For Model Pick": (
                _num(row.get("_market_decision_home_spread")) if str(row.get("Model Pick")) == str(row.get("Home Team"))
                else -_num(row.get("_market_decision_home_spread"))
            ) if np.isfinite(_num(row.get("_market_decision_home_spread"))) else np.nan,
            "Model-Market Gap": (
                (
                    _num(row.get("_market_decision_home_spread")) if str(row.get("Model Pick")) == str(row.get("Home Team"))
                    else -_num(row.get("_market_decision_home_spread"))
                ) - _num(row.get("Fair Spread"))
            ) if np.isfinite(_num(row.get("_market_decision_home_spread"))) and np.isfinite(_num(row.get("Fair Spread"))) else np.nan,
            "Tracked Ticket Count": row.get("_market_ticket_count"),
            "Market Activity": row.get("_market_activity_level"),
            "Provider Signals": row.get("_market_provider_signals"),
            "Book Agreement": row.get("_market_book_agreement"),
            "Book Spread Range": row.get("_market_book_spread_range"),
            "Market Provider": row.get("_market_source_label"),
            "Split Provider": row.get("_market_split_source_label"),
            "Final Away Score": row.get("_final_away"), "Final Home Score": row.get("_final_home"),
            "Actual Home Margin": (_num(row.get("_final_home")) - _num(row.get("_final_away"))) if np.isfinite(_num(row.get("_final_home"))) and np.isfinite(_num(row.get("_final_away"))) else np.nan,
            "Absolute Final Margin": abs(_num(row.get("_final_home")) - _num(row.get("_final_away"))) if np.isfinite(_num(row.get("_final_home"))) and np.isfinite(_num(row.get("_final_away"))) else np.nan,
        })
    return pd.DataFrame(rows)
