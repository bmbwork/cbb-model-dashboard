#!/usr/bin/env python3
"""Refresh the server-side CBB Stats Lab cache from CollegeBasketballData.

This worker is intentionally downstream of the frozen forecasting model. It does
not alter model inputs, predictions, grades, sportsbook data, or model promotion
state. CBBD credentials remain in the worker environment and are never written
to the database or dashboard.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
import sys
import time
from typing import Any, Iterable

import requests
from supabase import create_client

CBBD_BASE_URL = "https://api.collegebasketballdata.com"
TEAM_TABLE = "cbb_stats_team_season"
PLAYER_TABLE = "cbb_stats_player_season"
TEAM_SHOOTING_TABLE = "cbb_stats_team_shooting"
PLAYER_SHOOTING_TABLE = "cbb_stats_player_shooting"


class CbbdError(RuntimeError):
    pass


def current_season(now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    # CBBD seasons are keyed to the fall start of the basketball season.
    return now.year if now.month >= 7 else now.year - 1


def fetch_json(
    session: requests.Session,
    api_key: str,
    path: str,
    params: dict[str, Any],
    *,
    attempts: int = 3,
) -> list[dict[str, Any]]:
    url = f"{CBBD_BASE_URL}{path}"
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(
                url,
                params={k: v for k, v in params.items() if v not in (None, "")},
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
                timeout=60,
            )
            if response.status_code in {401, 403}:
                raise CbbdError(f"CBBD denied {path} with HTTP {response.status_code}")
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise CbbdError(f"CBBD {path} returned {type(payload).__name__}, expected list")
            return [dict(item) for item in payload if isinstance(item, dict)]
        except (requests.RequestException, ValueError, CbbdError) as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(attempt * 1.5)
    raise CbbdError(f"CBBD request failed for {path}: {type(last_error).__name__}") from last_error


def chunks(rows: list[dict[str, Any]], size: int = 250) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def upsert_rows(client: Any, table: str, rows: list[dict[str, Any]], conflict: str) -> int:
    count = 0
    for batch in chunks(rows):
        client.table(table).upsert(batch, on_conflict=conflict).execute()
        count += len(batch)
    return count


def team_cache_rows(
    payload: list[dict[str, Any]], season: int, season_type: str, refreshed_at: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload:
        team_id = item.get("teamId")
        team = str(item.get("team") or "").strip()
        if team_id is None or not team:
            continue
        rows.append(
            {
                "season": int(item.get("season") or season),
                "season_type": season_type,
                "team_id": int(team_id),
                "team": team,
                "conference": item.get("conference"),
                "games": item.get("games"),
                "wins": item.get("wins"),
                "losses": item.get("losses"),
                "total_minutes": item.get("totalMinutes"),
                "pace": item.get("pace"),
                "payload": item,
                "refreshed_at": refreshed_at,
            }
        )
    return rows


def player_cache_rows(
    payload: list[dict[str, Any]], season: int, season_type: str, refreshed_at: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload:
        team_id = item.get("teamId")
        athlete_id = item.get("athleteId")
        team = str(item.get("team") or "").strip()
        name = str(item.get("name") or "").strip()
        if team_id is None or athlete_id is None or not team or not name:
            continue
        rows.append(
            {
                "season": int(item.get("season") or season),
                "season_type": season_type,
                "team_id": int(team_id),
                "team": team,
                "conference": item.get("conference"),
                "athlete_id": int(athlete_id),
                "name": name,
                "position": item.get("position"),
                "games": item.get("games"),
                "starts": item.get("starts"),
                "minutes": item.get("minutes"),
                "payload": item,
                "refreshed_at": refreshed_at,
            }
        )
    return rows


def team_shooting_cache_rows(
    payload: list[dict[str, Any]], season: int, season_type: str, refreshed_at: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload:
        team_id = item.get("teamId")
        team = str(item.get("team") or "").strip()
        if team_id is None or not team:
            continue
        rows.append(
            {
                "season": int(item.get("season") or season),
                "season_type": season_type,
                "team_id": int(team_id),
                "team": team,
                "conference": item.get("conference"),
                "tracked_shots": item.get("trackedShots"),
                "payload": item,
                "refreshed_at": refreshed_at,
            }
        )
    return rows


def player_shooting_cache_rows(
    payload: list[dict[str, Any]], season: int, season_type: str, refreshed_at: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload:
        team_id = item.get("teamId")
        athlete_id = item.get("athleteId")
        team = str(item.get("team") or "").strip()
        name = str(item.get("athleteName") or item.get("name") or "").strip()
        if team_id is None or athlete_id is None or not team or not name:
            continue
        rows.append(
            {
                "season": int(item.get("season") or season),
                "season_type": season_type,
                "team_id": int(team_id),
                "team": team,
                "conference": item.get("conference"),
                "athlete_id": int(athlete_id),
                "name": name,
                "position": item.get("position"),
                "tracked_shots": item.get("trackedShots"),
                "payload": item,
                "refreshed_at": refreshed_at,
            }
        )
    return rows


def unique_scope_values(team_payload: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    conferences = sorted(
        {str(row.get("conference") or "").strip() for row in team_payload if str(row.get("conference") or "").strip()}
    )
    independent_teams = sorted(
        {
            str(row.get("team") or "").strip()
            for row in team_payload
            if not str(row.get("conference") or "").strip() and str(row.get("team") or "").strip()
        }
    )
    return conferences, independent_teams


def fetch_shooting_scopes(
    session: requests.Session,
    api_key: str,
    path: str,
    season: int,
    season_type: str,
    team_payload: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    conferences, independent_teams = unique_scope_values(team_payload)
    combined: dict[tuple[Any, ...], dict[str, Any]] = {}
    warnings: list[str] = []

    scopes: list[dict[str, str]] = [{"conference": c} for c in conferences]
    scopes.extend({"team": team} for team in independent_teams)

    for scope in scopes:
        try:
            records = fetch_json(
                session,
                api_key,
                path,
                {"season": season, "seasonType": season_type, **scope},
                attempts=2,
            )
        except CbbdError as exc:
            label = scope.get("conference") or scope.get("team") or "unknown"
            warnings.append(f"{path} scope {label}: {exc}")
            continue
        for row in records:
            key = (
                row.get("teamId"),
                row.get("athleteId"),
                row.get("team"),
                row.get("athleteName"),
            )
            combined[key] = row
    return list(combined.values()), warnings


def refresh(season: int, season_type: str, include_shooting: bool) -> dict[str, Any]:
    api_key = os.environ.get("CBBD_API_KEY", "").strip()
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.environ.get("SUPABASE_SECRET_KEY", "").strip()
    )
    if not api_key:
        raise RuntimeError("CBBD_API_KEY is not configured")
    if not supabase_url or not supabase_key:
        raise RuntimeError("Supabase server credentials are not configured")

    refreshed_at = datetime.now(timezone.utc).isoformat()
    session = requests.Session()
    client = create_client(supabase_url, supabase_key)

    team_payload = fetch_json(
        session,
        api_key,
        "/stats/team/season",
        {"season": season, "seasonType": season_type},
    )
    player_payload = fetch_json(
        session,
        api_key,
        "/stats/player/season",
        {"season": season, "seasonType": season_type},
    )

    team_rows = team_cache_rows(team_payload, season, season_type, refreshed_at)
    player_rows = player_cache_rows(player_payload, season, season_type, refreshed_at)

    result: dict[str, Any] = {
        "season": season,
        "season_type": season_type,
        "team_source_rows": len(team_payload),
        "player_source_rows": len(player_payload),
        "team_rows": upsert_rows(client, TEAM_TABLE, team_rows, "season,season_type,team_id"),
        "player_rows": upsert_rows(
            client,
            PLAYER_TABLE,
            player_rows,
            "season,season_type,team_id,athlete_id",
        ),
        "team_shooting_rows": 0,
        "player_shooting_rows": 0,
        "warnings": [],
    }

    if include_shooting and team_payload:
        team_shooting, team_warnings = fetch_shooting_scopes(
            session,
            api_key,
            "/stats/team/shooting/season",
            season,
            season_type,
            team_payload,
        )
        player_shooting, player_warnings = fetch_shooting_scopes(
            session,
            api_key,
            "/stats/player/shooting/season",
            season,
            season_type,
            team_payload,
        )
        result["warnings"] = team_warnings + player_warnings
        result["team_shooting_rows"] = upsert_rows(
            client,
            TEAM_SHOOTING_TABLE,
            team_shooting_cache_rows(team_shooting, season, season_type, refreshed_at),
            "season,season_type,team_id",
        )
        result["player_shooting_rows"] = upsert_rows(
            client,
            PLAYER_SHOOTING_TABLE,
            player_shooting_cache_rows(player_shooting, season, season_type, refreshed_at),
            "season,season_type,team_id,athlete_id",
        )

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=current_season())
    parser.add_argument(
        "--season-type",
        choices=["regular", "postseason", "preseason"],
        default="regular",
    )
    parser.add_argument("--no-shooting", action="store_true")
    args = parser.parse_args()

    result = refresh(args.season, args.season_type, not args.no_shooting)
    print(
        "CBB Stats Lab refresh complete: "
        f"season={result['season']} type={result['season_type']} "
        f"teams={result['team_rows']} players={result['player_rows']} "
        f"team_shooting={result['team_shooting_rows']} "
        f"player_shooting={result['player_shooting_rows']}"
    )
    warnings = result.get("warnings") or []
    if warnings:
        print(f"Shooting enrichment warnings: {len(warnings)}", file=sys.stderr)
        for warning in warnings[:10]:
            print(f"- {warning}", file=sys.stderr)
    if result["team_rows"] == 0 or result["player_rows"] == 0:
        raise RuntimeError("CBBD returned no core team/player season statistics for the requested season")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
