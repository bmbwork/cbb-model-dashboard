from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from .market import normalize_team_name

CONSENSUS_URL = "https://www.scoresandodds.com/ncaab/consensus-picks"
USER_AGENT = "StatFactory-CBB/1.0 consensus collector"
_PERCENT_RE = re.compile(r"(?<!\d)(100|[1-9]?\d(?:\.\d+)?)%")
_SPREAD_RE = re.compile(r"\(([+-]\d+(?:\.\d+)?)\)")
_TOTAL_RE = re.compile(r"\([ou]([0-9]+(?:\.\d+)?)\)", re.I)
_BOOK_KEYS = {"bet365","betmgm","caesars","circa","draftkings","fanatics","fanduel","hardrock","pinnacle","betrivers"}
CONSENSUS_STALE_AFTER = pd.Timedelta(hours=2)


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _key(value: Any) -> str:
    return "".join(ch for ch in normalize_team_name(value).lower() if ch.isalnum())


def fetch_consensus_html(timeout: float = 30.0) -> str:
    response = requests.get(CONSENSUS_URL, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}, timeout=timeout)
    response.raise_for_status()
    if "Consensus Picks" not in response.text or "% of Bets" not in response.text:
        raise RuntimeError("CBB consensus page did not contain the expected public betting markers")
    return response.text


def _market_node(marker: Tag) -> Tag | None:
    node: Tag | None = marker
    for _ in range(10):
        if node is None:
            return None
        text = _text(node.get_text(" ", strip=True))
        if text.count("% of Bets") == 1 and text.count("% of Money") == 1 and len(_PERCENT_RE.findall(text)) == 4 and len(text) <= 650:
            return node
        node = node.parent if isinstance(node.parent, Tag) else None
    return None


def _candidate_teams(node: Tag, known: dict[str, str]) -> list[str]:
    found: list[str] = []
    for image in node.find_all("img"):
        alt = _text(image.get("alt"))
        key = _key(alt)
        if key and key not in _BOOK_KEYS and key in known and known[key] not in found:
            found.append(known[key])
    return found


def parse_consensus_html(html: str, *, known_teams: list[str]) -> list[dict[str, Any]]:
    known = {_key(team): str(team) for team in known_teams if _key(team)}
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    for text_node in soup.find_all(string=lambda value: value and "% of Bets" in str(value)):
        marker = text_node.parent
        if not isinstance(marker, Tag):
            continue
        market = _market_node(marker)
        if market is None or id(market) in seen:
            continue
        seen.add(id(market))
        node: Tag | None = market
        pair: list[str] = []
        for _ in range(12):
            if node is None:
                break
            pair = _candidate_teams(node, known)
            if len(pair) == 2:
                break
            if len(pair) > 2:
                pair = []
                break
            node = node.parent if isinstance(node.parent, Tag) else None
        if len(pair) != 2:
            continue
        label = _text(market.get_text(" ", strip=True))
        pct = [float(x) for x in _PERCENT_RE.findall(label)]
        if len(pct) != 4 or not (99 <= pct[0] + pct[1] <= 101 and 99 <= pct[2] + pct[3] <= 101):
            continue
        if "over" in label.lower() and "under" in label.lower():
            market_type, sides = "total", ("total_over","total_under")
            lines = [float(x) for x in _TOTAL_RE.findall(label)]
        elif len(_SPREAD_RE.findall(label)) >= 2:
            market_type, sides = "spread", ("spread_away","spread_home")
            lines = [float(x) for x in _SPREAD_RE.findall(label)]
        else:
            market_type, sides, lines = "moneyline", ("moneyline_away","moneyline_home"), []
        for i, side in enumerate(sides):
            rows.append({"away_team":pair[0],"home_team":pair[1],"market_type":market_type,"side":side,"line":lines[i] if len(lines)>i else None,"tickets_pct":pct[i],"handle_pct":pct[i+2]})
    deduped = {(r["away_team"],r["home_team"],r["market_type"],r["side"]):r for r in rows}
    return list(deduped.values())


def load_consensus_rows(public_client, slate_date: str) -> pd.DataFrame:
    try:
        data = public_client.table("cbb_consensus_splits").select("refresh_run_id,slate_date,game_id,market_type,side,line,tickets_pct,handle_pct,observed_at").eq("slate_date", slate_date).order("observed_at", desc=True).limit(3000).execute().data or []
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame(data)


def attach_aggregated_consensus(public_client, board: pd.DataFrame, slate_date: str, *, now: datetime | None = None) -> pd.DataFrame:
    out = board.copy()
    if out.empty:
        return out
    rows = load_consensus_rows(public_client, slate_date)
    out["_aggregate_public_available"] = False
    if rows.empty:
        return out
    rows["observed_at"] = pd.to_datetime(rows["observed_at"], utc=True, errors="coerce")
    current = pd.Timestamp(now or datetime.now(timezone.utc))
    if current.tzinfo is None:
        current = current.tz_localize("UTC")
    for idx, game in out.iterrows():
        game_id = str(game.get("Game ID") or "")
        g = rows[rows["game_id"].astype(str).eq(game_id)].sort_values("observed_at", ascending=False)
        if g.empty:
            continue
        refresh = str(g.iloc[0].get("refresh_run_id") or "")
        snap = g[g["refresh_run_id"].astype(str).eq(refresh)]
        if snap.empty:
            continue
        out.at[idx,"_aggregate_public_available"] = True
        last = snap["observed_at"].max()
        out.at[idx,"_aggregate_public_last_seen"] = None if pd.isna(last) else last.isoformat()
        for _, r in snap.iterrows():
            side = str(r.get("side") or "")
            prefix = {"spread_away":"spread_away","spread_home":"spread_home","moneyline_away":"ml_away","moneyline_home":"ml_home","total_over":"total_over","total_under":"total_under"}.get(side)
            if not prefix:
                continue
            out.at[idx,f"_aggregate_{prefix}_line"] = r.get("line")
            out.at[idx,f"_aggregate_{prefix}_tickets"] = r.get("tickets_pct")
            out.at[idx,f"_aggregate_{prefix}_money"] = r.get("handle_pct")
    return out


def aggregate_public_books_html(row: pd.Series) -> str:
    if not bool(row.get("_aggregate_public_available", False)):
        return ""
    away, home = str(row.get("Away Team") or "Away"), str(row.get("Home Team") or "Home")
    def pct(v):
        x = pd.to_numeric(v, errors="coerce")
        return "—" if pd.isna(x) else f"{float(x):.0f}%"
    def val(prefix):
        return f"{pct(row.get(f'_aggregate_{prefix}_money'))} money · {pct(row.get(f'_aggregate_{prefix}_tickets'))} bets"
    def line(prefix, total=False):
        x = pd.to_numeric(row.get(f"_aggregate_{prefix}_line"), errors="coerce")
        return "" if pd.isna(x) else (f" {float(x):.1f}" if total else f" {float(x):+.1f}")
    seen = pd.to_datetime(row.get("_aggregate_public_last_seen"), utc=True, errors="coerce")
    stamp = "" if pd.isna(seen) else seen.tz_convert("America/Chicago").strftime("%m/%d %-I:%M %p CT")
    sections = [
        ("SPREAD", f"{away}{line('spread_away')}", val("spread_away"), f"{home}{line('spread_home')}", val("spread_home")),
        ("MONEYLINE", away, val("ml_away"), home, val("ml_home")),
        ("TOTAL", f"Over{line('total_over', True)}", val("total_over"), f"Under{line('total_under', True)}", val("total_under")),
    ]
    body = "".join(f'<div class="aggregate-row"><span>{escape(title)}</span><div><b>{escape(a)}</b><em>{escape(av)}</em></div><div><b>{escape(b)}</b><em>{escape(bv)}</em></div></div>' for title,a,av,b,bv in sections)
    return f'<details class="aggregate-public"><summary>Aggregated public books</summary><p>Consensus across multiple public books · {escape(stamp)}. Separate from Owl sportsbook-specific splits; populations are never averaged together.</p>{body}</details>'


def _active_board(admin_client, now: datetime) -> pd.DataFrame:
    records = admin_client.table("cbb_slates").select("slate_date,revision,published_at,board_json").order("published_at", desc=True).limit(30).execute().data or []
    frames=[]
    for record in records:
        date = pd.to_datetime(record.get("slate_date"), errors="coerce")
        if pd.isna(date) or not (now.date()-timedelta(days=1) <= date.date() <= now.date()+timedelta(days=8)):
            continue
        frame=pd.DataFrame(record.get("board_json") or [])
        if frame.empty:
            continue
        frame["slate_date"] = str(record.get("slate_date"))
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    board=pd.concat(frames,ignore_index=True).drop_duplicates("Game ID",keep="first")
    kick=pd.to_datetime(board.get("Start Time UTC"),utc=True,errors="coerce")
    return board[kick.notna() & (kick > pd.Timestamp(now))].copy()


def collect_public_consensus(admin_client, *, now: datetime | None = None) -> dict[str, Any]:
    current=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stamp=current.isoformat(); run=f"cbb_consensus_{current.strftime('%Y%m%dT%H%M%S%fZ')}"
    admin_client.table("cbb_consensus_refresh_runs").insert({"refresh_run_id":run,"requested_at":stamp,"status":"running","source_url":CONSENSUS_URL}).execute()
    try:
        board=_active_board(admin_client,current)
        if board.empty:
            admin_client.table("cbb_consensus_refresh_runs").update({"completed_at":stamp,"status":"completed","requested_games":0,"parsed_matchups":0,"matched_events":0,"unmatched_active_events":0}).eq("refresh_run_id",run).execute()
            return {"refresh_run_id":run,"stored_rows":0}
        known=set(board["Away Team"].astype(str)).union(set(board["Home Team"].astype(str)))
        parsed=parse_consensus_html(fetch_consensus_html(),known_teams=list(known))
        lookup={(_key(r["Away Team"]),_key(r["Home Team"])):r for _,r in board.iterrows()}
        source_pairs={(r["away_team"],r["home_team"]) for r in parsed}
        matched=[]; events=set()
        for row in parsed:
            game=lookup.get((_key(row["away_team"]),_key(row["home_team"])))
            if game is None: continue
            matched.append({"refresh_run_id":run,"slate_date":str(game["slate_date"]),"game_id":str(game["Game ID"]),"market_type":row["market_type"],"side":row["side"],"line":row["line"],"tickets_pct":row["tickets_pct"],"handle_pct":row["handle_pct"],"observed_at":stamp}); events.add(str(game["Game ID"]))
        minimum=max(2,math.ceil(min(len(source_pairs),len(board))*0.20)) if source_pairs else 0
        if len(events)<minimum:
            raise RuntimeError(f"CBB consensus coverage failed closed: matched {len(events)} games; minimum={minimum}")
        for start in range(0,len(matched),500): admin_client.table("cbb_consensus_splits").insert(matched[start:start+500]).execute()
        values={"completed_at":stamp,"status":"completed","requested_games":len(board),"parsed_matchups":len(source_pairs),"matched_events":len(events),"unmatched_active_events":max(0,len(board)-len(events)),"diagnostics":{"stored_rows":len(matched)}}
        admin_client.table("cbb_consensus_refresh_runs").update(values).eq("refresh_run_id",run).execute()
        return {"refresh_run_id":run,"stored_rows":len(matched),**values}
    except Exception as exc:
        admin_client.table("cbb_consensus_refresh_runs").update({"completed_at":datetime.now(timezone.utc).isoformat(),"status":"failed","diagnostics":{"error":str(exc)}}).eq("refresh_run_id",run).execute()
        raise
