from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from html import escape
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd

_APPLIED = False
_ESPN_TEAMS = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams?limit=1000"
_ESPN_TEAM = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{slug}"
_ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates={date}&limit=500"
_DIRECTORY: dict[str, str] = {}
_DIRECTORY_ATTEMPTED_AT = 0.0
_SCOREBOARD_DIRECTORIES: dict[str, dict[str, str]] = {}
_SCOREBOARD_ATTEMPTED_AT: dict[str, float] = {}
_RETRY_SECONDS = 90.0
_LOGO_CACHE: dict[str, str] = {}

PREMIUM_CSS = r"""
<style>
.cbb-logo-matchup{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:.7rem;border:1px solid rgba(249,115,22,.20);border-radius:14px;background:linear-gradient(110deg,rgba(249,115,22,.075),rgba(20,10,12,.82),rgba(251,191,36,.035));padding:.62rem .7rem;margin:0 0 .62rem}.cbb-logo-team{display:flex;align-items:center;gap:.52rem;min-width:0}.cbb-logo-team.home{justify-content:flex-end;text-align:right}.cbb-logo-team img,.cbb-logo-fallback{width:2rem;height:2rem;object-fit:contain;flex:0 0 2rem}.cbb-logo-fallback{display:inline-flex;align-items:center;justify-content:center;border-radius:50%;background:rgba(249,115,22,.10);border:1px solid rgba(249,115,22,.28);color:#ffd0a8;font-size:.62rem;font-weight:900}.cbb-logo-team strong{display:block;color:#fff7f1;font-size:.83rem;line-height:1.1}.cbb-logo-team small{display:block;color:#a18479;font-size:.56rem;margin-top:.13rem}.cbb-logo-vs{color:#936f62;font-size:.62rem;font-weight:900}
.cbb-money-shell{border:1px solid rgba(249,115,22,.18);border-radius:14px;background:linear-gradient(145deg,rgba(27,11,14,.96),rgba(14,8,10,.98));padding:.72rem .76rem;margin:.64rem 0}.cbb-money-head{display:flex;align-items:center;justify-content:space-between;gap:.55rem;margin-bottom:.58rem}.cbb-money-head strong{color:#ffb56f;font-size:.67rem;letter-spacing:.08em}.cbb-money-head span{color:#927b73;font-size:.55rem}.cbb-money-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.52rem}.cbb-money-card{border:1px solid rgba(148,163,184,.11);border-radius:11px;background:linear-gradient(180deg,rgba(255,255,255,.024),rgba(255,255,255,.012));padding:.58rem .60rem;min-width:0}.cbb-money-title{color:#f5ded2;font-size:.59rem;font-weight:900;letter-spacing:.07em;margin-bottom:.34rem}.cbb-money-lead{color:#fff8f4;font-size:.70rem;font-weight:800;line-height:1.24;margin-bottom:.40rem;min-height:1.75em}.cbb-money-meter{position:relative;height:1.58rem;border-radius:8px;overflow:hidden;background:#271a1d;border:1px solid rgba(255,255,255,.07);box-shadow:inset 0 0 0 1px rgba(0,0,0,.12)}.cbb-money-fill{position:absolute;top:0;bottom:0;z-index:1}.cbb-money-fill.left{left:0;background:linear-gradient(90deg,#088f59,#20c982)}.cbb-money-fill.right{right:0;background:linear-gradient(90deg,#e84b5e,#f06470)}.cbb-money-pct{position:absolute;top:50%;transform:translateY(-50%);z-index:3;color:#fff;font-size:.61rem;font-weight:950;line-height:1;padding:.18rem .30rem;border-radius:999px;background:rgba(8,10,12,.68);border:1px solid rgba(255,255,255,.13);text-shadow:0 1px 2px rgba(0,0,0,.65);white-space:nowrap}.cbb-money-pct.left{left:.24rem}.cbb-money-pct.right{right:.24rem}.cbb-money-labels{display:flex;justify-content:space-between;gap:.42rem;color:#b9a197;font-size:.56rem;margin-top:.31rem}.cbb-money-labels span{min-width:0;overflow-wrap:anywhere}.cbb-ticket-line{color:#927f76;font-size:.54rem;margin-top:.32rem;line-height:1.34}.cbb-money-legend{display:flex;gap:.5rem;align-items:center;color:#806c64;font-size:.51rem;margin-top:.45rem}.cbb-money-legend i{display:inline-block;width:.42rem;height:.42rem;border-radius:50%;margin-right:.18rem}.cbb-money-legend .green{background:#20c982}.cbb-money-legend .red{background:#f06470}
@media(max-width:900px){.cbb-money-grid{grid-template-columns:1fr}.cbb-logo-team img,.cbb-logo-fallback{width:1.72rem;height:1.72rem;flex-basis:1.72rem}.cbb-logo-team strong{font-size:.75rem}}
</style>
"""


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").lower()
    text = text.replace("&", " and ").replace("(fl)", " fl ").replace("(oh)", " oh ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _fetch_json(url: str) -> dict:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {}
    try:
        req = Request(url, headers={"User-Agent": "StatFactory/1.0"})
        with urlopen(req, timeout=6.0) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return {}


def _team_record(team: dict) -> tuple[list[str], str]:
    logos = team.get("logos") or []
    href = str(team.get("logo") or "")
    if not href and logos and isinstance(logos[0], dict):
        href = str(logos[0].get("href") or "")
    team_id = str(team.get("id") or "").strip()
    if not href and team_id.isdigit():
        href = f"https://a.espncdn.com/i/teamlogos/ncaa/500/{team_id}.png"
    fields = [team.get(k) for k in ("displayName", "shortDisplayName", "name", "nickname", "location", "abbreviation", "slug")]
    return [x for x in (_norm(v) for v in fields) if x], href


def _add_team_to_directory(directory: dict[str, str], team: object) -> None:
    if not isinstance(team, dict):
        return
    keys, href = _team_record(team)
    if href:
        for key in keys:
            directory.setdefault(key, href)


def _team_directory() -> dict[str, str]:
    global _DIRECTORY, _DIRECTORY_ATTEMPTED_AT
    if _DIRECTORY:
        return _DIRECTORY
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {}
    now = time.time()
    if _DIRECTORY_ATTEMPTED_AT and now - _DIRECTORY_ATTEMPTED_AT < _RETRY_SECONDS:
        return {}
    _DIRECTORY_ATTEMPTED_AT = now
    payload = _fetch_json(_ESPN_TEAMS)
    directory: dict[str, str] = {}
    sports = payload.get("sports") or []
    leagues = sports[0].get("leagues") if sports and isinstance(sports[0], dict) else []
    entries = leagues[0].get("teams") if leagues and isinstance(leagues[0], dict) else []
    for wrapper in entries or []:
        team = wrapper.get("team", wrapper) if isinstance(wrapper, dict) else {}
        _add_team_to_directory(directory, team)
    if directory:
        _DIRECTORY = directory
    return _DIRECTORY


def _scoreboard_directory(game_date: str) -> dict[str, str]:
    date_key = re.sub(r"[^0-9]", "", str(game_date or ""))[:8]
    if len(date_key) != 8:
        return {}
    if _SCOREBOARD_DIRECTORIES.get(date_key):
        return _SCOREBOARD_DIRECTORIES[date_key]
    now = time.time()
    attempted = _SCOREBOARD_ATTEMPTED_AT.get(date_key, 0.0)
    if attempted and now - attempted < _RETRY_SECONDS:
        return {}
    _SCOREBOARD_ATTEMPTED_AT[date_key] = now
    payload = _fetch_json(_ESPN_SCOREBOARD.format(date=date_key))
    directory: dict[str, str] = {}
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        for competition in event.get("competitions") or []:
            if not isinstance(competition, dict):
                continue
            for competitor in competition.get("competitors") or []:
                if not isinstance(competitor, dict):
                    continue
                _add_team_to_directory(directory, competitor.get("team"))
    if directory:
        _SCOREBOARD_DIRECTORIES[date_key] = directory
    return directory


def _row_game_date(row: pd.Series) -> str:
    for field in ("Target Date", "V1.1.3 Target Date", "Start Time UTC", "_start_dt"):
        value = row.get(field)
        if value is None or str(value).strip() in {"", "NaT", "nan", "None"}:
            continue
        parsed = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.notna(parsed):
            return parsed.strftime("%Y%m%d")
        compact = re.sub(r"[^0-9]", "", str(value))[:8]
        if len(compact) == 8:
            return compact
    return ""


def team_logo_url(team_name: str, game_date: str = "") -> str:
    key = _norm(team_name)
    if not key:
        return ""
    if key in _LOGO_CACHE:
        return _LOGO_CACHE[key]
    aliases = {
        "miami fl": "miami hurricanes",
        "miami florida": "miami hurricanes",
        "nc state": "nc state wolfpack",
        "usc": "usc trojans",
        "ole miss": "ole miss rebels",
        "st john s": "st johns red storm",
        "saint mary s": "saint marys gaels",
    }
    candidates = tuple(x for x in (key, aliases.get(key, "")) if x)
    if game_date:
        scoreboard = _scoreboard_directory(game_date)
        for candidate in candidates:
            if scoreboard.get(candidate):
                _LOGO_CACHE[key] = scoreboard[candidate]
                return _LOGO_CACHE[key]
    directory = _team_directory()
    for candidate in candidates:
        if directory.get(candidate):
            _LOGO_CACHE[key] = directory[candidate]
            return _LOGO_CACHE[key]
    slug = quote(re.sub(r"\s+", "-", aliases.get(key, key)))
    payload = _fetch_json(_ESPN_TEAM.format(slug=slug))
    team = payload.get("team") if isinstance(payload, dict) else None
    if isinstance(team, dict):
        _, href = _team_record(team)
        if href:
            _LOGO_CACHE[key] = href
            return href
    return ""


def _logo_html(team: str, game_date: str = "") -> str:
    from .team_logos import bundled_logo_source
    url = bundled_logo_source(team) or team_logo_url(team, game_date)
    if url:
        return f'<img src="{escape(url, quote=True)}" alt="{escape(team)} logo" loading="lazy">'
    letters = "".join(part[:1] for part in str(team).split()[:2]).upper() or "SF"
    return f'<span class="cbb-logo-fallback">{escape(letters)}</span>'


def _finite(value: object) -> float | None:
    value = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(value) else float(value)


def _matchup_banner(row: pd.Series) -> str:
    away = str(row.get("Away Team") or "Away")
    home = str(row.get("Home Team") or "Home")
    game_date = _row_game_date(row)
    return '<div class="cbb-logo-matchup">' + f'<div class="cbb-logo-team away">{_logo_html(away, game_date)}<div><strong>{escape(away)}</strong><small>AWAY</small></div></div>' + '<div class="cbb-logo-vs">VS</div>' + f'<div class="cbb-logo-team home"><div><strong>{escape(home)}</strong><small>HOME</small></div>{_logo_html(home, game_date)}</div>' + '</div>'


def _line_team(team: str, line: object) -> str:
    number = _finite(line)
    return team if number is None else f"{team} {number:+.1f}"


def _money_card(title: str, left_label: str, lm: object, lt: object, right_label: str, rm: object, rt: object) -> str:
    left, right = _finite(lm), _finite(rm)
    if left is None or right is None or abs(left + right - 100.0) > 3.0:
        return ""
    total = left + right
    if total <= 0:
        return ""
    left_width = max(0.0, min(100.0, 100.0 * left / total))
    right_width = 100.0 - left_width
    leader, leader_pct = (left_label, left) if left >= right else (right_label, right)
    lead = f"Money heavily favors {leader}" if leader_pct >= 75 else (f"Money favors {leader}" if leader_pct >= 60 else f"Money leans {leader}")
    left_t, right_t = _finite(lt), _finite(rt)
    ticket = "Ticket split unavailable"
    if left_t is not None and right_t is not None and left_t + right_t > 0 and abs(left_t + right_t - 100.0) <= 3.0:
        ticket = f"Tickets: {left_label} {left_t:.0f}% · {right_label} {right_t:.0f}%"
    meter = (
        f'<div class="cbb-money-meter" aria-label="{escape(title)} handle share: {left:.0f}% versus {right:.0f}%">'
        f'<span class="cbb-money-fill left" style="width:{left_width:.1f}%"></span>'
        f'<span class="cbb-money-fill right" style="width:{right_width:.1f}%"></span>'
        f'<span class="cbb-money-pct left">{left:.0f}%</span><span class="cbb-money-pct right">{right:.0f}%</span></div>'
    )
    return '<div class="cbb-money-card">' + f'<div class="cbb-money-title">{escape(title)}</div><div class="cbb-money-lead">{escape(lead)}</div>' + meter + f'<div class="cbb-money-labels"><span>{escape(left_label)}</span><span>{escape(right_label)}</span></div><div class="cbb-ticket-line">{escape(ticket)}</div></div>'


def premium_betting_splits_html(row: pd.Series) -> str:
    away = str(row.get("Away Team") or "Away")
    home = str(row.get("Home Team") or "Home")
    spread_home_line = row.get("_market_current_home_spread")
    spread_away_line = row.get("_market_current_away_spread")
    total_line = _finite(row.get("_market_total_line"))
    over = "Over" if total_line is None else f"Over {total_line:.1f}"
    under = "Under" if total_line is None else f"Under {total_line:.1f}"
    cards = [
        _money_card("SPREAD MONEY", _line_team(away, spread_away_line), row.get("_market_away_money_pct"), row.get("_market_away_ticket_pct"), _line_team(home, spread_home_line), row.get("_market_home_money_pct"), row.get("_market_home_ticket_pct")),
        _money_card("MONEYLINE MONEY", away, row.get("_market_ml_away_money_pct"), row.get("_market_ml_away_ticket_pct"), home, row.get("_market_ml_home_money_pct"), row.get("_market_ml_home_ticket_pct")),
        _money_card("TOTAL MONEY", over, row.get("_market_total_over_money_pct"), row.get("_market_total_over_ticket_pct"), under, row.get("_market_total_under_money_pct"), row.get("_market_total_under_ticket_pct")),
    ]
    cards = [card for card in cards if card]
    source = str(row.get("_market_split_source_label") or "Owl Insight")
    if not cards:
        return '<div class="split-strip empty"><div class="split-strip-head"><span>BETTING SPLITS</span><em>No validated money split snapshot for this matchup</em></div></div>'
    legend = '<div class="cbb-money-legend"><span><i class="green"></i>left/away or over</span><span><i class="red"></i>right/home or under</span></div>'
    return f'<div class="cbb-money-shell"><div class="cbb-money-head"><strong>BETTING SPLITS · {escape(source.upper())}</strong><span>Money = handle share · tickets shown below</span></div><div class="cbb-money-grid">{"".join(cards)}</div>{legend}</div>'


def _snapshot_value(row: pd.Series, *names: str) -> float | None:
    for name in names:
        if name in row.index:
            value = _finite(row.get(name))
            if value is not None:
                return value
    return None


def _patch_market_attach() -> None:
    from . import market
    if getattr(market.attach_market_to_board, "_sf_premium", False):
        return
    original = market.attach_market_to_board

    def patched(board: pd.DataFrame, snapshots: pd.DataFrame, context: pd.DataFrame | None = None) -> pd.DataFrame:
        out = original(board, snapshots, context)
        new_fields = ("_market_current_away_spread", "_market_ml_away_ticket_pct", "_market_ml_away_money_pct", "_market_total_under_ticket_pct", "_market_total_under_money_pct")
        for field in new_fields:
            if field not in out.columns:
                out[field] = None
        if out.empty or snapshots is None or snapshots.empty:
            return out
        snap = snapshots.copy()
        gid_col = "Game ID" if "Game ID" in snap.columns else ("game_id" if "game_id" in snap.columns else None)
        market_col = "Market Type" if "Market Type" in snap.columns else ("market_type" if "market_type" in snap.columns else None)
        time_col = "Snapshot Time UTC" if "Snapshot Time UTC" in snap.columns else ("snapshot_time_utc" if "snapshot_time_utc" in snap.columns else None)
        if not gid_col or not market_col:
            return out
        if time_col:
            snap[time_col] = pd.to_datetime(snap[time_col], utc=True, errors="coerce")
        for idx, game in out.iterrows():
            gid = str(game.get("Game ID") or "")
            game_rows = snap[snap[gid_col].astype(str).eq(gid)].copy()
            if game_rows.empty:
                continue
            start = pd.to_datetime(game.get("_start_dt"), utc=True, errors="coerce")
            if time_col and pd.notna(start):
                game_rows = game_rows[game_rows[time_col].isna() | (game_rows[time_col] < start)]
            if game_rows.empty:
                continue

            def latest(kind: str) -> pd.Series | None:
                rows = game_rows[game_rows[market_col].astype(str).str.lower().eq(kind)].copy()
                if rows.empty:
                    return None
                if time_col:
                    rows = rows.sort_values(time_col)
                return rows.iloc[-1]

            spread = latest("spread")
            ml = latest("moneyline")
            total = latest("total")
            if spread is not None:
                out.at[idx, "_market_current_away_spread"] = _snapshot_value(spread, "Away Line", "away_line")
            if ml is not None:
                out.at[idx, "_market_ml_away_ticket_pct"] = _snapshot_value(ml, "Away Ticket %", "away_ticket_pct")
                out.at[idx, "_market_ml_away_money_pct"] = _snapshot_value(ml, "Away Money %", "away_money_pct")
            if total is not None:
                out.at[idx, "_market_total_under_ticket_pct"] = _snapshot_value(total, "Under Ticket %", "under_ticket_pct")
                out.at[idx, "_market_total_under_money_pct"] = _snapshot_value(total, "Under Money %", "under_money_pct")
        return out

    patched._sf_premium = True
    market.attach_market_to_board = patched


def _patch_intelligence() -> None:
    from . import intelligence
    if getattr(intelligence.game_card_html, "_sf_premium", False):
        return
    intelligence.betting_splits_html = premium_betting_splits_html
    original_card = intelligence.game_card_html

    def patched_card(row: pd.Series) -> str:
        base = original_card(row)
        end = base.find(">")
        if end < 0:
            return base
        return base[: end + 1] + _matchup_banner(row) + base[end + 1 :]

    patched_card._sf_premium = True
    intelligence.game_card_html = patched_card


def apply_premium_ui_patch() -> None:
    global _APPLIED
    if _APPLIED:
        return
    from . import ui
    if PREMIUM_CSS not in ui.GLOBAL_CSS:
        ui.GLOBAL_CSS += PREMIUM_CSS
    _patch_market_attach()
    _patch_intelligence()
    _APPLIED = True
