from __future__ import annotations

import json
import os
import re
import unicodedata
from functools import lru_cache
from html import escape
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd

_APPLIED = False
_ESPN_TEAMS = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams?limit=1000"
_ESPN_TEAM = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{slug}"

PREMIUM_CSS = r"""
<style>
.cbb-logo-matchup{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:.7rem;border:1px solid rgba(249,115,22,.20);border-radius:14px;background:linear-gradient(110deg,rgba(249,115,22,.075),rgba(20,10,12,.82),rgba(251,191,36,.035));padding:.62rem .7rem;margin:0 0 .62rem}.cbb-logo-team{display:flex;align-items:center;gap:.52rem;min-width:0}.cbb-logo-team.home{justify-content:flex-end;text-align:right}.cbb-logo-team img,.cbb-logo-fallback{width:2rem;height:2rem;object-fit:contain;flex:0 0 2rem}.cbb-logo-fallback{display:inline-flex;align-items:center;justify-content:center;border-radius:50%;background:rgba(249,115,22,.10);border:1px solid rgba(249,115,22,.28);color:#ffd0a8;font-size:.62rem;font-weight:900}.cbb-logo-team strong{display:block;color:#fff7f1;font-size:.83rem;line-height:1.1}.cbb-logo-team small{display:block;color:#a18479;font-size:.56rem;margin-top:.13rem}.cbb-logo-vs{color:#936f62;font-size:.62rem;font-weight:900}
.cbb-money-shell{border:1px solid rgba(249,115,22,.18);border-radius:14px;background:linear-gradient(145deg,rgba(27,11,14,.96),rgba(14,8,10,.98));padding:.68rem .72rem;margin:.64rem 0}.cbb-money-head{display:flex;align-items:center;justify-content:space-between;gap:.55rem;margin-bottom:.56rem}.cbb-money-head strong{color:#ffb56f;font-size:.67rem;letter-spacing:.08em}.cbb-money-head span{color:#927b73;font-size:.55rem}.cbb-money-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.5rem}.cbb-money-card{border:1px solid rgba(148,163,184,.10);border-radius:10px;background:rgba(255,255,255,.018);padding:.55rem .58rem}.cbb-money-title{color:#f5ded2;font-size:.59rem;font-weight:900;letter-spacing:.07em;margin-bottom:.33rem}.cbb-money-lead{color:#fff8f4;font-size:.70rem;font-weight:800;line-height:1.24;margin-bottom:.36rem;min-height:1.75em}.cbb-money-bar{height:1.32rem;display:flex;border-radius:7px;overflow:hidden;background:#271a1d;border:1px solid rgba(255,255,255,.06)}.cbb-money-bar .left,.cbb-money-bar .right{display:flex;align-items:center;color:white;font-size:.60rem;font-weight:950;padding:0 .31rem}.cbb-money-bar .left{justify-content:flex-start;background:linear-gradient(90deg,#0b9d62,#20c982)}.cbb-money-bar .right{justify-content:flex-end;background:linear-gradient(90deg,#ec4f61,#f06470)}.cbb-money-labels{display:flex;justify-content:space-between;gap:.3rem;color:#b0988d;font-size:.56rem;margin-top:.28rem}.cbb-ticket-line{color:#927f76;font-size:.54rem;margin-top:.30rem;line-height:1.32}
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
        with urlopen(req, timeout=1.8) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return {}


def _team_record(team: dict) -> tuple[list[str], str]:
    logos = team.get("logos") or []
    href = str(logos[0].get("href") or "") if logos and isinstance(logos[0], dict) else ""
    fields = [team.get(k) for k in ("displayName", "shortDisplayName", "name", "nickname", "location", "abbreviation", "slug")]
    return [x for x in (_norm(v) for v in fields) if x], href


@lru_cache(maxsize=1)
def _team_directory() -> dict[str, str]:
    payload = _fetch_json(_ESPN_TEAMS)
    out: dict[str, str] = {}
    sports = payload.get("sports") or []
    leagues = sports[0].get("leagues") if sports and isinstance(sports[0], dict) else []
    entries = leagues[0].get("teams") if leagues and isinstance(leagues[0], dict) else []
    for wrapper in entries or []:
        team = wrapper.get("team", wrapper) if isinstance(wrapper, dict) else {}
        if not isinstance(team, dict):
            continue
        keys, href = _team_record(team)
        if href:
            for key in keys:
                out.setdefault(key, href)
    return out


@lru_cache(maxsize=512)
def team_logo_url(team_name: str) -> str:
    key = _norm(team_name)
    if not key:
        return ""
    aliases = {"miami fl": "miami hurricanes", "miami florida": "miami hurricanes", "nc state": "nc state wolfpack", "usc": "usc trojans", "ole miss": "ole miss rebels"}
    directory = _team_directory()
    for candidate in (key, aliases.get(key, "")):
        if candidate and directory.get(candidate):
            return directory[candidate]
    payload = _fetch_json(_ESPN_TEAM.format(slug=quote(re.sub(r"\s+", "-", key))))
    team = payload.get("team") if isinstance(payload, dict) else None
    if isinstance(team, dict):
        _, href = _team_record(team)
        return href
    return ""


def _logo_html(team: str) -> str:
    url = team_logo_url(team)
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
    return '<div class="cbb-logo-matchup">' + f'<div class="cbb-logo-team away">{_logo_html(away)}<div><strong>{escape(away)}</strong><small>AWAY</small></div></div>' + '<div class="cbb-logo-vs">VS</div>' + f'<div class="cbb-logo-team home"><div><strong>{escape(home)}</strong><small>HOME</small></div>{_logo_html(home)}</div>' + '</div>'


def _line_team(team: str, line: object) -> str:
    number = _finite(line)
    return team if number is None else f"{team} {number:+.1f}"


def _money_card(title: str, left_label: str, lm: object, lt: object, right_label: str, rm: object, rt: object) -> str:
    left, right = _finite(lm), _finite(rm)
    if left is None or right is None or abs(left + right - 100.0) > 3.0:
        return ""
    width = max(0.0, min(100.0, left))
    leader, leader_pct = (left_label, left) if left >= right else (right_label, right)
    lead = f"Money heavily favors {leader}" if leader_pct >= 75 else (f"Money favors {leader}" if leader_pct >= 60 else f"Money leans {leader}")
    left_t, right_t = _finite(lt), _finite(rt)
    ticket = "Ticket split unavailable"
    if left_t is not None and right_t is not None and abs(left_t + right_t - 100.0) <= 3.0:
        ticket = f"Tickets: {left_label} {left_t:.0f}% · {right_label} {right_t:.0f}%"
    return '<div class="cbb-money-card">' + f'<div class="cbb-money-title">{escape(title)}</div><div class="cbb-money-lead">{escape(lead)}</div>' + f'<div class="cbb-money-bar"><span class="left" style="width:{width:.1f}%">{left:.0f}%</span><span class="right" style="width:{100-width:.1f}%">{right:.0f}%</span></div>' + f'<div class="cbb-money-labels"><span>{escape(left_label)}</span><span>{escape(right_label)}</span></div><div class="cbb-ticket-line">{escape(ticket)}</div></div>'


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
    return f'<div class="cbb-money-shell"><div class="cbb-money-head"><strong>BETTING SPLITS · {escape(source.upper())}</strong><span>Money = handle share · tickets shown below</span></div><div class="cbb-money-grid">{"".join(cards)}</div></div>'


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
