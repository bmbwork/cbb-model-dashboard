#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from typing import Any

import pandas as pd

from cbb_dashboard.best_odds_archive import archive_event_key, extract_best_odds_records
from cbb_dashboard.owlsinsight_odds_provider import (
    DEFAULT_BOOKS,
    OwlsInsightOddsConfig,
    OwlsInsightOddsProvider,
)

TABLE = "cbb_owls_best_odds_archive"
CARD_VIEW = "cbb_owls_best_odds_card_state"
CLOSE_WINDOW_MINUTES = int(os.getenv("CBB_CLOSE_WINDOW_MINUTES", "25"))
LOOKAHEAD_DAYS = int(os.getenv("CBB_ARCHIVE_LOOKAHEAD_DAYS", "45"))


def required_env(name: str, *alternates: str) -> str:
    for key in (name, *alternates):
        value = str(os.getenv(key, "") or "").strip()
        if value:
            return value
    raise RuntimeError(f"Required environment variable is missing: {name}")


def rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    return [dict(x) for x in (data or [])]


def now_utc() -> pd.Timestamp:
    return pd.Timestamp(datetime.now(timezone.utc))


def current_window(client: Any, now: pd.Timestamp) -> list[dict[str, Any]]:
    lo = (now - pd.Timedelta(hours=24)).isoformat()
    hi = (now + pd.Timedelta(days=LOOKAHEAD_DAYS)).isoformat()
    response = (
        client.table(CARD_VIEW)
        .select("*")
        .gte("commence_time_utc", lo)
        .lte("commence_time_utc", hi)
        .order("captured_at_utc", desc=False)
        .limit(20000)
        .execute()
    )
    return rows(response)


def event_state(existing: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for row in existing:
        key = str(row.get("archive_event_key") or "")
        if not key:
            continue
        item = state.setdefault(key, {"roles": set(), "market_roles": {}, "rows": []})
        role = str(row.get("snapshot_role") or "").lower()
        market = str(row.get("market_type") or "").lower()
        item["roles"].add(role)
        if market:
            item["market_roles"].setdefault(market, set()).add(role)
        item["rows"].append(row)
    return state


def due_close_keys(existing: list[dict[str, Any]], now: pd.Timestamp) -> set[str]:
    state = event_state(existing)
    due: set[str] = set()
    for key, item in state.items():
        market_roles = item.get("market_roles", {})
        tracked_markets = {m for m in ("spread", "moneyline") if m in market_roles}
        if tracked_markets and all("close" in market_roles.get(m, set()) for m in tracked_markets):
            continue
        first = item["rows"][0]
        start = pd.to_datetime(first.get("commence_time_utc"), utc=True, errors="coerce")
        if pd.isna(start):
            continue
        mins = (start - now).total_seconds() / 60.0
        if 0 <= mins <= CLOSE_WINDOW_MINUTES:
            due.add(key)
    return due


def finalize_missed_closes(existing: list[dict[str, Any]], now: pd.Timestamp) -> list[dict[str, Any]]:
    """If a scheduler run was missed, preserve the last known pregame quote as tracked close."""
    state = event_state(existing)
    inserts: list[dict[str, Any]] = []
    for key, item in state.items():
        event_rows = item["rows"]
        market_roles = item.get("market_roles", {})
        start = pd.to_datetime(event_rows[0].get("commence_time_utc"), utc=True, errors="coerce")
        if pd.isna(start) or start > now:
            continue
        for market in ("spread", "moneyline"):
            if "close" in market_roles.get(market, set()):
                continue
            candidates = [
                r for r in event_rows
                if str(r.get("market_type") or "").lower() == market
                and str(r.get("snapshot_role") or "").lower() != "close"
            ]
            if not candidates:
                continue
            candidates.sort(key=lambda r: pd.to_datetime(r.get("captured_at_utc"), utc=True, errors="coerce"))
            row = dict(candidates[-1])
            for key_to_drop in ("id", "created_at"):
                row.pop(key_to_drop, None)
            row["snapshot_role"] = "close"
            row["capture_trigger"] = "finalize_last_pregame"
            payload = {
                "archive_event_key": row.get("archive_event_key"),
                "market_type": row.get("market_type"),
                "captured_at_utc": row.get("captured_at_utc"),
                "snapshot_role": "close",
                "best_home_line": row.get("best_home_line"),
                "best_home_price": row.get("best_home_price"),
                "best_home_book_key": row.get("best_home_book_key"),
                "best_away_line": row.get("best_away_line"),
                "best_away_price": row.get("best_away_price"),
                "best_away_book_key": row.get("best_away_book_key"),
            }
            row["raw_snapshot_hash"] = hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
            inserts.append(row)
    return inserts


def upsert(client: Any, records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    response = client.table(TABLE).upsert(records, on_conflict="raw_snapshot_hash").execute()
    data = rows(response)
    return len(data) if data else len(records)


def provider_event_key(event: dict[str, Any]) -> str:
    return archive_event_key(event.get("home_team"), event.get("away_team"), event.get("commence_time"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive best available Owls NCAAB ML/spread prices.")
    parser.add_argument("--mode", choices=("hourly", "close"), default="hourly")
    args = parser.parse_args()

    api_key = required_env("OWLS_INSIGHT_API_KEY")
    supabase_url = required_env("SUPABASE_URL")
    supabase_key = required_env("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY")
    books = str(os.getenv("OWLS_INSIGHT_ODDS_BOOKS", DEFAULT_BOOKS) or DEFAULT_BOOKS)

    from supabase import create_client

    client = create_client(supabase_url, supabase_key)
    now = now_utc()
    existing = current_window(client, now)

    missed = finalize_missed_closes(existing, now)
    missed_count = upsert(client, missed)
    if missed_count:
        print(f"Finalized {missed_count} missed close row(s) using the last stored pregame snapshot.")
        existing = current_window(client, now)

    wanted_keys: set[str] | None = None
    if args.mode == "close":
        wanted_keys = due_close_keys(existing, now)
        if not wanted_keys:
            print("No games need a near-tip close capture. Owls API call skipped.")
            return 0

    provider = OwlsInsightOddsProvider(OwlsInsightOddsConfig(api_key=api_key, books=books))
    payload = provider.current_odds()
    meta = payload.get("meta", {}) if isinstance(payload, dict) and isinstance(payload.get("meta"), dict) else {}
    events = provider._coalesce_events(payload)
    state = event_state(existing)
    response_timestamp = meta.get("timestamp")

    inserts: list[dict[str, Any]] = []
    event_count = 0
    for event in events:
        start = pd.to_datetime(event.get("commence_time"), utc=True, errors="coerce")
        if pd.isna(start) or start <= now or start > now + pd.Timedelta(days=LOOKAHEAD_DAYS):
            continue
        key = provider_event_key(event)
        if wanted_keys is not None and key not in wanted_keys:
            continue
        market_roles = state.get(key, {}).get("market_roles", {})
        initial_role = "open" if not state.get(key) else "observed"
        event_rows = extract_best_odds_records(
            event,
            captured_at=now,
            response_timestamp=response_timestamp,
            snapshot_role=initial_role,
            capture_trigger="scheduled_hourly" if args.mode == "hourly" else "scheduled_close_guard",
        )
        if event_rows:
            event_count += 1
            inserts.extend(event_rows)
        mins_to_tip = (start - now).total_seconds() / 60.0
        should_close = 0 <= mins_to_tip <= CLOSE_WINDOW_MINUTES
        if should_close:
            close_rows = extract_best_odds_records(
                event,
                captured_at=now,
                response_timestamp=response_timestamp,
                snapshot_role="close",
                capture_trigger="scheduled_close_guard",
            )
            inserts.extend(
                row for row in close_rows
                if "close" not in market_roles.get(str(row.get("market_type") or "").lower(), set())
            )

    written = upsert(client, inserts)
    print(
        f"Owls best-odds archive complete: mode={args.mode} provider_events={len(events)} "
        f"eligible_events={event_count} rows_written={written}."
    )
    freshness = meta.get("freshness") if isinstance(meta.get("freshness"), dict) else {}
    if freshness:
        print(f"Owls freshness: ageSeconds={freshness.get('ageSeconds')} stale={freshness.get('stale')}")
    if provider.last_rate_headers:
        print(
            "Owls rate limits: "
            f"minute={provider.last_rate_headers.get('remaining_minute') or 'n/a'} "
            f"month={provider.last_rate_headers.get('remaining_month') or 'n/a'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
