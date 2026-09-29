"""CBB Stats Lab: server-side Supabase reader and filterable Streamlit UI.

The CBBD API key never enters this module. A background worker caches provider
responses in server-only Supabase tables; this page reads those tables with the
Streamlit server secret key after the Stat Factory access gate has already run.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

TEAM_TABLE = "cbb_stats_team_season"
PLAYER_TABLE = "cbb_stats_player_season"
TEAM_SHOOTING_TABLE = "cbb_stats_team_shooting"
PLAYER_SHOOTING_TABLE = "cbb_stats_player_shooting"

TABLE_LABELS = {
    TEAM_TABLE: "Team Stats",
    PLAYER_TABLE: "Player Stats",
    TEAM_SHOOTING_TABLE: "Team Shooting",
    PLAYER_SHOOTING_TABLE: "Player Shooting",
}

FRIENDLY_COLUMNS = {
    "season": "Season",
    "seasonLabel": "Season Label",
    "teamId": "Team ID",
    "team": "Team",
    "conference": "Conference",
    "athleteId": "Athlete ID",
    "athleteSourceId": "Athlete Source ID",
    "name": "Player",
    "athleteName": "Player",
    "position": "Position",
    "games": "Games",
    "starts": "Starts",
    "minutes": "Minutes",
    "points": "Points",
    "assists": "Assists",
    "steals": "Steals",
    "blocks": "Blocks",
    "turnovers": "Turnovers",
    "fouls": "Fouls",
    "usage": "Usage",
    "pace": "Pace",
    "wins": "Wins",
    "losses": "Losses",
    "offensiveRating": "Offensive Rating",
    "defensiveRating": "Defensive Rating",
    "netRating": "Net Rating",
    "PORPAG": "PORPAG",
    "effectiveFieldGoalPct": "eFG%",
    "trueShootingPct": "True Shooting %",
    "assistsTurnoverRatio": "Assist/Turnover Ratio",
    "freeThrowRate": "Free Throw Rate",
    "offensiveReboundPct": "Offensive Rebound %",
    "trackedShots": "Tracked Shots",
    "assistedPct": "Assisted %",
}


def _admin_client(store: Any) -> Any:
    if store is None:
        raise RuntimeError("Stats storage is not configured.")
    return store._admin_client()


def _data(response: Any) -> list[dict[str, Any]]:
    payload = getattr(response, "data", None)
    return [dict(row) for row in (payload or [])]


@st.cache_data(ttl=900, show_spinner=False)
def stats_catalog(_store: Any) -> list[dict[str, Any]]:
    client = _admin_client(_store)
    response = (
        client.table(TEAM_TABLE)
        .select("season,season_type,refreshed_at")
        .order("season", desc=True)
        .limit(5000)
        .execute()
    )
    seen: set[tuple[int, str]] = set()
    catalog: list[dict[str, Any]] = []
    for row in _data(response):
        key = (int(row.get("season") or 0), str(row.get("season_type") or "regular"))
        if key[0] <= 0 or key in seen:
            continue
        seen.add(key)
        catalog.append(
            {
                "season": key[0],
                "season_type": key[1],
                "refreshed_at": row.get("refreshed_at"),
            }
        )
    return sorted(catalog, key=lambda x: (x["season"], x["season_type"]), reverse=True)


@st.cache_data(ttl=900, show_spinner=False)
def stats_rows(_store: Any, table: str, season: int, season_type: str) -> list[dict[str, Any]]:
    client = _admin_client(_store)
    rows: list[dict[str, Any]] = []
    page_size = 1000
    start = 0
    while True:
        response = (
            client.table(table)
            .select("*")
            .eq("season", int(season))
            .eq("season_type", str(season_type))
            .order("team", desc=False)
            .range(start, start + page_size - 1)
            .execute()
        )
        batch = _data(response)
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
        if start >= 20000:
            break
    return rows


def _flatten_payload(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    payloads: list[dict[str, Any]] = []
    refreshed: list[Any] = []
    for row in rows:
        payload = row.get("payload")
        payloads.append(dict(payload) if isinstance(payload, dict) else {})
        refreshed.append(row.get("refreshed_at"))
    frame = pd.json_normalize(payloads, sep=".")
    frame["_refreshed_at"] = refreshed
    return frame


def _friendly_name(column: str) -> str:
    if column in FRIENDLY_COLUMNS:
        return FRIENDLY_COLUMNS[column]
    parts = column.split(".")
    pretty: list[str] = []
    for part in parts:
        if part in FRIENDLY_COLUMNS:
            pretty.append(FRIENDLY_COLUMNS[part])
        else:
            text = part.replace("_", " ")
            text = "".join((" " + ch if ch.isupper() else ch) for ch in text).strip()
            pretty.append(text.title())
    return " · ".join(pretty)


def _friendly_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    renamed = {_col: _friendly_name(_col) for _col in frame.columns if not _col.startswith("_")}
    return frame.rename(columns=renamed)


def _numeric_columns(frame: pd.DataFrame) -> list[str]:
    cols: list[str] = []
    for col in frame.columns:
        if col.startswith("_"):
            continue
        series = pd.to_numeric(frame[col], errors="coerce")
        if series.notna().sum() >= max(1, min(5, len(frame))):
            cols.append(col)
    return cols


def _default_columns(frame: pd.DataFrame, mode: str) -> list[str]:
    if frame.empty:
        return []
    if mode == "team":
        preferred = [
            "Team", "Conference", "Games", "Wins", "Losses", "Pace",
            "Team Stats · Points · Total", "Team Stats · Rating",
            "Team Stats · True Shooting", "Team Stats · Four Factors · Effective Field Goal Pct",
            "Team Stats · Four Factors · Turnover Ratio",
            "Team Stats · Four Factors · Offensive Rebound Pct",
            "Team Stats · Rebounds · Total", "Team Stats · Assists",
            "Opponent Stats · Points · Total", "Opponent Stats · Rating",
        ]
    elif mode == "player":
        preferred = [
            "Player", "Team", "Conference", "Position", "Games", "Starts", "Minutes",
            "Points", "Assists", "Rebounds · Total", "Steals", "Blocks", "Turnovers",
            "Usage", "Offensive Rating", "Defensive Rating", "Net Rating", "PORPAG",
            "eFG%", "True Shooting %", "Win Shares · Total",
        ]
    elif mode == "team_shooting":
        preferred = [
            "Team", "Conference", "Tracked Shots", "Assisted %", "Free Throw Rate",
            "Dunks · Pct", "Layups · Pct", "Two Point Jumpers · Pct",
            "Three Point Jumpers · Pct", "Attempts Breakdown · Three Rate",
        ]
    else:
        preferred = [
            "Player", "Team", "Conference", "Tracked Shots", "Assisted %", "Free Throw Rate",
            "Dunks · Pct", "Layups · Pct", "Two Point Jumpers · Pct",
            "Three Point Jumpers · Pct",
        ]
    return [c for c in preferred if c in frame.columns][:22]


def _filter_frame(frame: pd.DataFrame, key_prefix: str, entity_col: str) -> pd.DataFrame:
    if frame.empty:
        return frame

    conferences = sorted(
        {str(x) for x in frame.get("Conference", pd.Series(dtype=object)).dropna().tolist() if str(x).strip()}
    )
    teams = sorted(
        {str(x) for x in frame.get("Team", pd.Series(dtype=object)).dropna().tolist() if str(x).strip()}
    )

    with st.form(f"{key_prefix}_filters"):
        c1, c2, c3, c4 = st.columns([1.25, 1.5, 1.4, 1.0])
        with c1:
            selected_conferences = st.multiselect("Conference", conferences, key=f"{key_prefix}_conference")
        with c2:
            selected_teams = st.multiselect("Team", teams, key=f"{key_prefix}_team")
        with c3:
            search = st.text_input(
                "Search",
                placeholder=f"Search {entity_col.lower()}...",
                key=f"{key_prefix}_search",
            )
        with c4:
            min_games = st.number_input(
                "Min games",
                min_value=0,
                max_value=50,
                value=0,
                step=1,
                key=f"{key_prefix}_min_games",
            )
        st.form_submit_button("GO", use_container_width=True)

    filtered = frame.copy()
    if selected_conferences and "Conference" in filtered:
        filtered = filtered[filtered["Conference"].isin(selected_conferences)]
    if selected_teams and "Team" in filtered:
        filtered = filtered[filtered["Team"].isin(selected_teams)]
    if search and entity_col in filtered:
        filtered = filtered[
            filtered[entity_col].astype(str).str.contains(search, case=False, na=False)
        ]
    if min_games and "Games" in filtered:
        games = pd.to_numeric(filtered["Games"], errors="coerce").fillna(0)
        filtered = filtered[games >= float(min_games)]
    return filtered


def _render_table(frame: pd.DataFrame, mode: str, key_prefix: str, entity_col: str) -> None:
    if frame.empty:
        st.info("No rows match these filters.")
        return

    numeric = _numeric_columns(frame)
    default_sort = next(
        (candidate for candidate in ["Points", "Wins", "Net Rating", "Tracked Shots", "Games"] if candidate in numeric),
        numeric[0] if numeric else None,
    )

    sort_col: str | None = None
    descending = True
    s1, s2 = st.columns([2.2, 1])
    with s1:
        if numeric:
            sort_col = st.selectbox(
                "Sort by",
                numeric,
                index=numeric.index(default_sort) if default_sort in numeric else 0,
                key=f"{key_prefix}_sort",
            )
    with s2:
        descending = st.toggle("Descending", value=True, key=f"{key_prefix}_desc")

    sorted_frame = frame.copy()
    if sort_col:
        sorted_frame["_sort_metric"] = pd.to_numeric(sorted_frame[sort_col], errors="coerce")
        sorted_frame = sorted_frame.sort_values(
            ["_sort_metric", entity_col] if entity_col in sorted_frame else ["_sort_metric"],
            ascending=[not descending, True] if entity_col in sorted_frame else [not descending],
            na_position="last",
        ).drop(columns=["_sort_metric"])

    all_columns = [c for c in sorted_frame.columns if not c.startswith("_")]
    defaults = _default_columns(sorted_frame, mode) or all_columns[:18]
    show_all = st.toggle("Show every tracked field", value=False, key=f"{key_prefix}_all_fields")
    if show_all:
        selected_columns = all_columns
    else:
        selected_columns = st.multiselect(
            "Columns",
            all_columns,
            default=defaults,
            key=f"{key_prefix}_columns",
        )
        if not selected_columns:
            selected_columns = defaults

    st.caption(f"{len(sorted_frame):,} matching rows · {len(all_columns):,} tracked fields available")
    st.dataframe(
        sorted_frame[selected_columns],
        use_container_width=True,
        hide_index=True,
        height=min(820, 78 + 35 * min(len(sorted_frame), 20)),
    )


def _render_mode(
    store: Any,
    table: str,
    season: int,
    season_type: str,
    mode: str,
    entity_col: str,
    key_prefix: str,
) -> None:
    rows = stats_rows(store, table, season, season_type)
    frame = _friendly_frame(_flatten_payload(rows))
    if frame.empty:
        st.info(f"No {TABLE_LABELS[table].lower()} have been cached for this season yet.")
        return
    filtered = _filter_frame(frame, key_prefix, entity_col)
    _render_table(filtered, mode, key_prefix, entity_col)


def _format_refresh(value: Any) -> str:
    if not value:
        return "Unknown"
    try:
        return pd.to_datetime(value, utc=True).strftime("%b %d, %Y %H:%M UTC")
    except Exception:
        return str(value)


def render_stats_lab(store: Any) -> None:
    st.markdown('<div class="cbb-kicker">STAT FACTORY · COLLEGE BASKETBALL</div>', unsafe_allow_html=True)
    st.markdown('<div class="cbb-title">CBB <span style="color:#f97316">STATS LAB</span></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="cbb-subtitle">One searchable research surface for team and player statistics, opponent production, shooting profiles and advanced metrics.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="firewall-note"><strong>Stats layer:</strong> sourced from CollegeBasketballData and cached server-side. These statistics are research context and do not rewrite the frozen CBB forecasting model.</div>',
        unsafe_allow_html=True,
    )

    try:
        catalog = stats_catalog(store)
    except Exception as exc:
        st.warning(
            "Stats Lab storage is not available to this deployment yet. "
            f"Server read failed: {type(exc).__name__}."
        )
        return

    if not catalog:
        st.info("Stats Lab is ready, but no CBBD season has been ingested yet.")
        return

    season_labels = [
        f"{item['season']} · {str(item['season_type']).title()}" for item in catalog
    ]
    selected_label = st.selectbox("Season", season_labels, index=0)
    selected_index = season_labels.index(selected_label)
    selected = catalog[selected_index]
    season = int(selected["season"])
    season_type = str(selected["season_type"])

    team_rows = stats_rows(store, TEAM_TABLE, season, season_type)
    player_rows = stats_rows(store, PLAYER_TABLE, season, season_type)
    team_frame = _friendly_frame(_flatten_payload(team_rows))
    player_frame = _friendly_frame(_flatten_payload(player_rows))
    conferences = (
        int(team_frame["Conference"].dropna().nunique())
        if "Conference" in team_frame
        else 0
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Teams", f"{len(team_frame):,}")
    m2.metric("Players", f"{len(player_frame):,}")
    m3.metric("Conferences", f"{conferences:,}")
    m4.metric("Last refresh", _format_refresh(selected.get("refreshed_at")))

    team_tab, player_tab, team_shooting_tab, player_shooting_tab = st.tabs(
        ["TEAM STATS", "PLAYER STATS", "TEAM SHOOTING", "PLAYER SHOOTING"]
    )

    with team_tab:
        st.subheader("Team Statistics")
        st.caption(
            "Includes record, pace, shooting, Four Factors, possessions, rating, "
            "rebounding, turnovers, assists, steals, blocks, scoring splits and the "
            "same opponent statistics for defensive context."
        )
        _render_mode(
            store,
            TEAM_TABLE,
            season,
            season_type,
            "team",
            "Team",
            f"stats_team_{season}_{season_type}",
        )

    with player_tab:
        st.subheader("Player Statistics")
        st.caption(
            "Includes traditional production plus usage, offensive/defensive/net "
            "rating, PORPAG, eFG%, true shooting, free-throw rate, offensive rebound "
            "rate, shooting detail and win shares where CBBD provides them."
        )
        _render_mode(
            store,
            PLAYER_TABLE,
            season,
            season_type,
            "player",
            "Player",
            f"stats_player_{season}_{season_type}",
        )

    with team_shooting_tab:
        st.subheader("Team Shot Profile")
        _render_mode(
            store,
            TEAM_SHOOTING_TABLE,
            season,
            season_type,
            "team_shooting",
            "Team",
            f"stats_team_shooting_{season}_{season_type}",
        )

    with player_shooting_tab:
        st.subheader("Player Shot Profile")
        _render_mode(
            store,
            PLAYER_SHOOTING_TABLE,
            season,
            season_type,
            "player_shooting",
            "Player",
            f"stats_player_shooting_{season}_{season_type}",
        )
