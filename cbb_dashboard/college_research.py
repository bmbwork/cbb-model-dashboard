"""Read-only season evidence and price-aware college research.

This module never changes a published forecast, grade, or retained quote. It
summarizes verified completed games and uses one paired sportsbook observation.
"""
from __future__ import annotations

from html import escape
from functools import lru_cache
import math
import re
import unicodedata

import numpy as np
import pandas as pd


def number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (ValueError, TypeError):
        return None
    return value if math.isfinite(value) else None


def stamp(value):
    return pd.to_datetime(value, utc=True, errors="coerce")


def _true(value):
    return isinstance(value, (bool, np.bool_)) and bool(value)


def _key(value):
    raw = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", raw.replace("&", "and"))


@lru_cache(maxsize=4096)
def team_key(value):
    # The bundled directory excludes ambiguous aliases. Never fuzzy-join two
    # similarly named schools, or compare provider-native IDs with ESPN IDs.
    from .team_logos import _directory
    record = _directory().get(_key(value))
    return "espn:" + str(record["id"]) if record else _key(value)


def season_for_row(row):
    day = stamp(row.get("Target Date", row.get("Start Time UTC")))
    return day.year + (day.month >= 7) if pd.notna(day) else None


def fair_spread_for_pick(row):
    pick = str(row.get("Model Pick") or "")
    home, away = str(row.get("Home Team") or ""), str(row.get("Away Team") or "")
    home_line = number(row.get("Fair Home Spread"))
    if pick not in (home, away):
        return None
    if home_line is not None:
        return home_line if pick == home else -home_line
    # Older frozen files may omit the home handicap but retain both point
    # projections. Convert those points rather than guessing a favorite's sign.
    hs, aws = number(row.get("Projected Home Score")), number(row.get("Projected Away Score"))
    return (aws - hs if pick == home else hs - aws) if hs is not None and aws is not None else None


def _game_for_team(game, key, cutoff):
    if not str(game.get("event_id") or "").strip() or not game.get("home_team") or not game.get("away_team"):
        return None
    if team_key(game.get("home_team")) == team_key(game.get("away_team")):
        return None
    start, known = stamp(game.get("start_time")), stamp(game.get("completed_at") or game.get("fetched_at"))
    if pd.isna(start) or pd.isna(known) or not (start <= known <= cutoff) or start >= cutoff:
        return None
    h, a = number(game.get("home_score")), number(game.get("away_score"))
    if h is None or a is None or min(h, a) < 0 or not h.is_integer() or not a.is_integer() or h == a:
        return None
    if not str(game.get("result_source") or "").strip():
        return None
    is_home = team_key(game.get("home_team")) == key
    if not is_home and team_key(game.get("away_team")) != key:
        return None
    opp = "away" if is_home else "home"
    score, opponent_score = (h, a) if is_home else (a, h)
    rank = number(game.get(opp + "_rank"))
    ranking_time = stamp(game.get("ranking_as_of"))
    ranking_source = str(game.get("ranking_source") or "")
    ranked = (_true(game.get("rankings_verified")) and rank is not None and rank.is_integer()
              and 1 <= rank <= 25 and pd.notna(ranking_time) and ranking_time <= start
              and bool(re.search(r"\bAP\b|Associated Press", ranking_source, re.I)))
    ot = number(game.get("overtimes"))
    return {"event_id": str(game.get("event_id") or ""), "played_at": start.isoformat(),
            "opponent": str(game.get(opp + "_team") or ""), "opponent_rank": int(rank) if ranked else None,
            "score": int(score), "opponent_score": int(opponent_score), "result": "W" if score > opponent_score else "L",
            "venue": "neutral" if _true(game.get("neutral_site")) else "home" if is_home else "away",
            "overtimes": int(ot) if ot is not None and ot.is_integer() and ot > 0 else None,
            "source": str(game.get("result_source")), "source_url": str(game.get("result_source_url") or "")}


def team_research(team, games, coverage, cutoff, now, season, *, eligible=True):
    key = team_key(team)
    matched = [g for g in games if team_key(g.get("home_team")) == key or team_key(g.get("away_team")) == key]
    valid = [_game_for_team(g, key, cutoff) for g in matched]
    dedup, conflicts = {}, set()
    for g in (g for g in valid if g is not None):
        if g["event_id"] in dedup and dedup[g["event_id"]] != g:
            conflicts.add(g["event_id"])
        dedup[g["event_id"]] = g
    dedup = {event: g for event, g in dedup.items() if event not in conflicts}
    completed = sorted(dedup.values(), key=lambda g: (g["played_at"], g["event_id"]), reverse=True)
    through, begin = stamp(coverage.get("complete_through")), stamp(coverage.get("complete_from"))
    season_start = pd.Timestamp(year=season - 1, month=7, day=1, tz="UTC")
    covered = coverage.get("covered_teams")
    team_covered = isinstance(covered, list) and any(isinstance(name, str) and team_key(name) == key for name in covered)
    partial_refresh = any(pd.notna(stamp(g.get("fetched_at"))) and pd.notna(through) and stamp(g.get("fetched_at")) > through for g in matched)
    complete = (_true(coverage.get("complete")) and team_covered and not partial_refresh and pd.notna(through) and pd.notna(begin)
                and begin <= season_start and through <= now + pd.Timedelta(minutes=5)
                and (through >= cutoff or (cutoff == now and now - through <= pd.Timedelta(hours=24))))
    # Later-fetched games without an official completion time cannot establish
    # what was known before a historical tip. Withhold that historical record.
    unknown_before = any(pd.notna(stamp(g.get("start_time"))) and stamp(g.get("start_time")) < cutoff
                         and not g.get("completed_at") and stamp(g.get("fetched_at")) > cutoff for g in matched)
    unusable_before = any(pd.notna(stamp(g.get("completed_at") or g.get("fetched_at")))
                          and stamp(g.get("completed_at") or g.get("fetched_at")) <= cutoff and parsed is None
                          for g, parsed in zip(matched, valid))
    record = None
    if eligible and complete and completed and not unknown_before and not unusable_before and not conflicts:
        wins = sum(g["result"] == "W" for g in completed)
        record = {"wins": wins, "losses": len(completed) - wins, "as_of": cutoff.isoformat()}
    notable = [g for g in completed if g["opponent_rank"] is not None]
    return {"team": team, "record": record, "games": len(completed),
            "ranked_wins": sum(g["result"] == "W" for g in notable),
            "notable": notable[:5], "as_of": cutoff.isoformat(),
            "coverage_complete": bool(complete and eligible and not unknown_before and not unusable_before and not conflicts),
            "source": str(coverage.get("source") or "")}


def _quote_pairs(row, snapshots, now):
    start = stamp(row.get("Start Time UTC"))
    if pd.isna(start) or start <= now or snapshots is None or snapshots.empty:
        return {}
    candidates = snapshots.loc[snapshots["Game ID"].astype(str) == str(row.get("Game ID"))].copy()
    if candidates.empty:
        return {}
    candidates["_time"] = pd.to_datetime(candidates["Snapshot Time UTC"], utc=True, errors="coerce")
    candidates = candidates.loc[candidates["_time"].notna() & (candidates["_time"] <= now) & (candidates["_time"] < start)]
    result = {}
    pick_home = row.get("Model Pick") == row.get("Home Team")
    for _, q in candidates.sort_values("_time", ascending=False).iterrows():
        kind = str(q.get("Market Type") or "")
        if kind not in ("spread", "moneyline") or kind in result:
            continue
        hp, ap = number(q.get("Home Price")), number(q.get("Away Price"))
        label = str(q.get("Source Label") or "")
        match = re.fullmatch(r"Owls Insight · ([^·]+)", label)
        if not match or re.search(r"consensus|multiple|comparison", label, re.I):
            continue
        if hp is None or ap is None or abs(hp) < 100 or abs(ap) < 100:
            continue
        hl, al = number(q.get("Home Line")), number(q.get("Away Line"))
        if kind == "spread" and (hl is None or al is None or abs(hl + al) > .01):
            continue
        result[kind] = {"book": match[1], "at": q["_time"].isoformat(),
                        "fresh": now - q["_time"] <= pd.Timedelta(minutes=90),
                        "line": hl if pick_home else al, "price": hp if pick_home else ap}
    return result


def attach_college_research(board, history, coverage_rows, snapshots=None, *, now=None, published_at=None):
    """Attach private display evidence to a copy after market/archive attachment."""
    out = board.copy()
    now = stamp(now if now is not None else pd.Timestamp.now(tz="UTC"))
    for col in ("_college_home", "_college_away", "_college_quotes", "_college_published_at"):
        out[col] = pd.Series([None] * len(out), index=out.index, dtype=object)
    indexes = {}
    for game in history:
        if game.get("sport") != "cbb":
            continue
        season = number(game.get("season"))
        for side in ("home", "away"):
            indexes.setdefault((season, team_key(game.get(side + "_team"))), []).append(game)
    for idx, row in out.iterrows():
        season = season_for_row(row)
        start = stamp(row.get("Start Time UTC"))
        cutoff = min(now, start) if pd.notna(start) else now
        coverage = next((c for c in coverage_rows if number(c.get("season")) == season and _true(c.get("complete"))), {})
        if season is not None:
            for prefix in ("Home", "Away"):
                games = indexes.get((season, team_key(row.get(prefix + " Team"))), [])
                out.at[idx, "_college_" + prefix.lower()] = team_research(str(row.get(prefix + " Team") or ""), games, coverage, cutoff, now, season, eligible=not (prefix + " D1" in row and not _true(row.get(prefix + " D1"))))
        out.at[idx, "_college_quotes"] = _quote_pairs(row, snapshots, now)
        out.at[idx, "_college_published_at"] = published_at
    return out


def research_for_team(row, team):
    prefix = "home" if str(row.get("Home Team") or "") == team else "away"
    value = row.get("_college_" + prefix)
    return value if isinstance(value, dict) else {"team": team, "record": None, "notable": [], "ranked_wins": 0, "games": 0}


def team_record_label(row, team):
    record = research_for_team(row, team).get("record")
    return f"{team} ({record['wins']}-{record['losses']})" if record else team


def _result_fact(g):
    action = "beat" if g["result"] == "W" else "lost to"
    venue = "on a neutral court" if g["venue"] == "neutral" else "at home" if g["venue"] == "home" else "on the road"
    ot = f" in {g['overtimes']}OT" if g.get("overtimes") else ""
    return f"{action} AP #{g['opponent_rank']} {g['opponent']} {g['score']}-{g['opponent_score']} {venue}{ot}"


def assessment(row):
    pick = str(row.get("Model Pick") or "the model pick")
    info = research_for_team(row, pick)
    opponent = str(row.get("Away Team") if pick == row.get("Home Team") else row.get("Home Team"))
    record = info.get("record")
    if not record:
        text = f"We cannot judge {pick}'s overall season reliably yet: a complete season record is not verified for this matchup."
    else:
        total = record["wins"] + record["losses"]
        pct = record["wins"] / total if total else 0
        if total < 8:
            text = f"It is too early to call {pick} a good team: they are {record['wins']}-{record['losses']} through only {total} verified games."
        elif pct >= .7 and info["ranked_wins"] >= 1:
            text = f"Yes — {pick} has a strong case: they are {record['wins']}-{record['losses']} and have {info['ranked_wins']} win{'s' if info['ranked_wins'] != 1 else ''} over opponents ranked in the AP Top 25 at tipoff."
        elif pct >= .5:
            text = f"{pick} has a mixed case at {record['wins']}-{record['losses']}; that record alone does not establish them as a strong team."
        else:
            text = f"No — {pick} has struggled this season at {record['wins']}-{record['losses']}, even though the model favors them in this particular matchup."
    facts = info.get("notable", [])[:3]
    if facts:
        text += " Their ranked-opponent results include: " + "; ".join(_result_fact(g) for g in facts) + "."
    else:
        text += " No verified result against an AP-ranked opponent is available in the captured history before this game."
    other = research_for_team(row, opponent).get("record")
    if other:
        text += f" {opponent} comes in at {other['wins']}-{other['losses']}."
    return text


def bottom_line(row, *, now=None):
    now = stamp(now if now is not None else pd.Timestamp.now(tz="UTC"))
    pick = str(row.get("Model Pick") or "the model pick")
    chance = number(row.get("Win Probability"))
    fair = fair_spread_for_pick(row)
    intro = f"The model gives {pick} a {chance * 100:.1f}% chance to win" if chance is not None and 0 <= chance <= 1 else "The model win probability is not verified"
    if fair is not None:
        intro += f" and a fair spread of {pick} {fair:+.1f}"
    intro += ". "
    start = stamp(row.get("Start Time UTC"))
    if pd.isna(start) or now >= start:
        return intro + "Pass on a new pregame play: this is historical/post-start research or the tipoff time is unverified."
    pub = stamp(row.get("_college_published_at"))
    run = stamp(row.get("Model Run At UTC"))
    if not ((pd.notna(pub) and pub < start) or (pd.notna(run) and run < start)):
        return intro + "Pass for now: pregame publication timing is not verified."
    if ("Deployment Eligible" in row and not _true(row.get("Deployment Eligible"))) or ("D1 Evaluation Eligible" in row and not _true(row.get("D1 Evaluation Eligible"))):
        return intro + "Pass: this forecast is outside the validated prospective deployment population."
    quotes = row.get("_college_quotes")
    quotes = quotes if isinstance(quotes, dict) else {}
    ml = quotes.get("moneyline")
    if ml and ml.get("fresh") and chance is not None and 0 <= chance <= 1:
        price = ml["price"]
        implied = 100 / (price + 100) if price > 0 else -price / (-price + 100)
        if chance - implied >= .03:
            label = "underdog moneyline" if price > 0 else "moneyline"
            return intro + f"{label.capitalize()} lean: {pick} {price:+.0f} at {ml['book']}. The model chance is {(chance-implied)*100:.1f} percentage points above that price's break-even rate. Recheck line movement and splits before taking this captured price."
    spread = quotes.get("spread")
    if spread and spread.get("fresh") and fair is not None and spread.get("line") is not None and spread["line"] - fair >= 2:
        narrow = " The winner lean is narrow; be cautious." if chance is not None and chance < .58 else ""
        return intro + f"Spread lean: {pick} {spread['line']:+.1f} at {spread['book']} gives {spread['line']-fair:.1f} more points than the model fair line. That is a line-value comparison, not an estimated cover probability.{narrow} Recheck movement and splits."
    if not any(q.get("fresh") for q in quotes.values()):
        return intro + "Pass for now: a fresh, paired sportsbook quote is not available."
    return intro + "Pass at the captured prices: the comparison does not show enough value for a play."


RESEARCH_CSS = '<style>.college-assessment{border:1px solid #395348;border-radius:12px;padding:14px;margin:10px 0;background:rgba(12,30,21,.55)}.college-assessment h3{font-size:1rem;color:#e4f8ed;margin:0 0 8px}.college-assessment p{font-size:.85rem;line-height:1.6;margin:5px 0;color:#c9d6ce}.college-notable{margin:12px 0;border:1px solid #39473e;border-radius:10px;padding:10px}.college-notable summary{cursor:pointer;font-weight:800;color:#e4f8ed}.college-notable-team{margin:10px 0}.college-notable table{width:100%;font-size:.75rem;border-collapse:collapse}.college-notable td,.college-notable th{padding:7px 5px;text-align:left;border-bottom:1px solid #293b31}.college-notable small{color:#9aada2}.college-notable .win{color:#64dea2}.college-notable .loss{color:#fb8994}</style>'


def notable_results_html(row):
    teams = []
    for prefix in ("Away", "Home"):
        name = str(row.get(prefix + " Team") or "")
        info = research_for_team(row, name)
        body = []
        for g in info.get("notable", [])[:5]:
            venue = "N" if g["venue"] == "neutral" else "@" if g["venue"] == "away" else "v"
            ot = f" ({g['overtimes']}OT)" if g.get("overtimes") else ""
            date = stamp(g["played_at"]).tz_convert("America/Chicago").strftime("%b %d")
            body.append(f'<tr><td>{date}</td><td>{escape(name)} {venue} AP #{g["opponent_rank"]} {escape(g["opponent"])}</td><td class="{"win" if g["result"] == "W" else "loss"}">{g["score"]}-{g["opponent_score"]} ({g["result"]}){ot}</td></tr>')
        table = '<table><thead><tr><th>Date</th><th>Matchup</th><th>Result</th></tr></thead><tbody>' + ''.join(body) + '</tbody></table>' if body else '<p>No verified AP-ranked opponent results are available before this matchup.</p>'
        as_of = stamp(info.get("as_of"))
        as_of_text = as_of.tz_convert("America/Chicago").strftime("%b %d, %Y · %I:%M %p %Z") if pd.notna(as_of) else "this matchup"
        record_note = f'Season record as of {as_of_text}.' if info.get("record") else 'Season record not fully verified before this matchup.'
        sources = sorted({g.get("source", "") for g in info.get("notable", []) if g.get("source")})
        source_note = ' Results: '+', '.join(sources)+'.' if sources else ''
        teams.append(f'<section class="college-notable-team"><strong>{escape(team_record_label(row,name))}</strong>{table}<small>{escape(record_note + source_note)}</small></section>')
    return '<details class="college-notable"><summary>Notable W/Ls</summary><small>Up to five most recent results per team against opponents ranked in the AP Top 25 at tipoff. Scores are from the named team’s perspective; N = neutral court.</small>'+''.join(teams)+'</details>'


def college_research_html(row):
    pick = str(row.get("Model Pick") or "the model pick")
    return RESEARCH_CSS + f'<section class="college-assessment"><h3>Is {escape(pick)} actually good?</h3><p>{escape(assessment(row))}</p><h3>Bottom Line</h3><p>{escape(bottom_line(row))}</p></section>' + notable_results_html(row)
