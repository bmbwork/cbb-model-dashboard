from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from html import unescape
from urllib.request import Request, urlopen

import pandas as pd

STANDINGS_URL = "https://site.web.api.espn.com/apis/v2/sports/basketball/mens-college-basketball/standings?level=3"
CONFERENCE_ALL = "All games"
CONFERENCE_GAMES = "Conference games"
NON_CONFERENCE_GAMES = "Non-conference games"
CONFERENCE_FILTERS = [CONFERENCE_ALL, CONFERENCE_GAMES, NON_CONFERENCE_GAMES]

_DIRECTORY: dict[str, str] = {}
_DIRECTORY_ATTEMPTED_AT = 0.0
_RETRY_SECONDS = 120.0


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", unescape(str(value or ""))).encode("ascii", "ignore").decode("ascii").lower()
    text = text.replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _is_independent(conference: object) -> bool:
    key = _norm(conference)
    return "independent" in key


def _conference_name(node: dict) -> str:
    for key in ("name", "shortName", "abbreviation", "displayName"):
        value = str(node.get(key) or "").strip()
        if value:
            return value
    return ""


def _team_keys(team: dict) -> list[str]:
    fields = [team.get(k) for k in ("displayName", "shortDisplayName", "name", "nickname", "location", "abbreviation", "slug")]
    return [key for key in (_norm(value) for value in fields) if key]


def _walk_group(node: dict, conference: str, out: dict[str, str]) -> None:
    if not isinstance(node, dict):
        return
    standings = node.get("standings") or {}
    entries = standings.get("entries") if isinstance(standings, dict) else []
    for entry in entries or []:
        team = entry.get("team") if isinstance(entry, dict) else None
        if not isinstance(team, dict):
            continue
        for key in _team_keys(team):
            out.setdefault(key, conference)
    teams = node.get("teams") or []
    for wrapper in teams:
        team = wrapper.get("team", wrapper) if isinstance(wrapper, dict) else None
        if not isinstance(team, dict):
            continue
        for key in _team_keys(team):
            out.setdefault(key, conference)
    for child in node.get("children") or []:
        _walk_group(child, conference, out)


def parse_conference_directory(payload: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    children = payload.get("children") or [] if isinstance(payload, dict) else []
    for group in children:
        if not isinstance(group, dict):
            continue
        conference = _conference_name(group)
        if conference:
            _walk_group(group, conference, out)
    return out


def conference_directory() -> dict[str, str]:
    """Return a successful ESPN D-I conference directory.

    Failures are retried and never alter the frozen CBB forecast; this metadata
    exists only to power discovery filters and conference labels.
    """
    global _DIRECTORY, _DIRECTORY_ATTEMPTED_AT
    if _DIRECTORY:
        return _DIRECTORY
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {}
    now = time.time()
    if _DIRECTORY_ATTEMPTED_AT and now - _DIRECTORY_ATTEMPTED_AT < _RETRY_SECONDS:
        return {}
    _DIRECTORY_ATTEMPTED_AT = now
    try:
        request = Request(STANDINGS_URL, headers={"User-Agent": "StatFactory/1.0"})
        with urlopen(request, timeout=6.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return {}
    directory = parse_conference_directory(payload)
    if directory:
        _DIRECTORY = directory
    return _DIRECTORY


def _row_value(row: pd.Series, names: tuple[str, ...]) -> str:
    for name in names:
        value = str(row.get(name) or "").strip()
        if value and value.lower() not in {"nan", "none"}:
            return value
    return ""


def _lookup(team: object, directory: dict[str, str]) -> str:
    key = _norm(team)
    if not key:
        return ""
    aliases = {
        "miami fl": "miami",
        "miami florida": "miami",
        "nc state": "north carolina state",
        "usc": "southern california",
        "ole miss": "mississippi",
    }
    for candidate in (key, aliases.get(key, "")):
        if candidate and candidate in directory:
            return directory[candidate]
    return ""


def attach_conference_context(frame: pd.DataFrame, directory: dict[str, str] | None = None) -> pd.DataFrame:
    out = frame.copy()
    if out.empty:
        for column in ("Home Conference", "Away Conference", "Conference Game", "_conference_known"):
            if column not in out.columns:
                out[column] = pd.Series(dtype="object")
        return out
    directory = conference_directory() if directory is None else directory
    homes: list[str] = []
    aways: list[str] = []
    known: list[bool] = []
    conference_game: list[bool] = []
    for _, row in out.iterrows():
        home = _row_value(row, ("Home Conference", "home_conference", "_home_conference")) or _lookup(row.get("Home Team"), directory)
        away = _row_value(row, ("Away Conference", "away_conference", "_away_conference")) or _lookup(row.get("Away Team"), directory)
        is_known = bool(home and away)
        same_conference = bool(
            is_known
            and _norm(home) == _norm(away)
            and not _is_independent(home)
            and not _is_independent(away)
        )
        homes.append(home)
        aways.append(away)
        known.append(is_known)
        conference_game.append(same_conference)
    out["Home Conference"] = homes
    out["Away Conference"] = aways
    out["Conference Game"] = conference_game
    out["_conference_known"] = known
    return out


def filter_conference_status(frame: pd.DataFrame, mode: str) -> pd.DataFrame:
    mode = str(mode or CONFERENCE_ALL)
    if mode == CONFERENCE_ALL or frame.empty:
        return frame.copy()
    work = attach_conference_context(frame) if "_conference_known" not in frame.columns else frame.copy()
    known = work.get("_conference_known", pd.Series(False, index=work.index)).fillna(False).astype(bool)
    same = work.get("Conference Game", pd.Series(False, index=work.index)).fillna(False).astype(bool)
    if mode == CONFERENCE_GAMES:
        return work.loc[known & same].copy()
    if mode == NON_CONFERENCE_GAMES:
        return work.loc[known & ~same].copy()
    raise ValueError(f"Unknown conference filter: {mode}")
