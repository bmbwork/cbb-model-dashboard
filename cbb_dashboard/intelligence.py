from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .ui import esc, fmt_num, fmt_odds, fmt_pct, fmt_spread


def confidence_band(row: pd.Series) -> str:
    p = float(pd.to_numeric(row.get("Win Probability"), errors="coerce") or 0.5)
    if p >= 0.75:
        return "strong"
    if p < 0.58:
        return "tossup"
    return "standard"


def translation_direction(row: pd.Series) -> str:
    adj = pd.to_numeric(row.get("Schedule Translation Margin Adj"), errors="coerce")
    if pd.isna(adj) or abs(float(adj)) < 0.05:
        return "No material schedule translation"
    team = row.get("Home Team") if float(adj) > 0 else row.get("Away Team")
    return f"{abs(float(adj)):.1f} pts toward {team}"


def signal_readout(row: pd.Series) -> tuple[list[str], list[str]]:
    positives: list[str] = []
    risks: list[str] = []
    pick = str(row.get("Model Pick") or "")
    home = str(row.get("Home Team") or "")
    away = str(row.get("Away Team") or "")
    pick_is_home = pick == home

    home_net = pd.to_numeric(row.get("Home AdjNet"), errors="coerce")
    away_net = pd.to_numeric(row.get("Away AdjNet"), errors="coerce")
    if pd.notna(home_net) and pd.notna(away_net):
        diff = float(home_net - away_net)
        signed = diff if pick_is_home else -diff
        if signed >= 3:
            positives.append(f"Adjusted net efficiency favors {pick} by {signed:.1f} points per 100 possessions.")
        elif signed <= -3:
            risks.append(f"Adjusted net efficiency actually favors the opponent by {abs(signed):.1f} per 100.")

    hsos = pd.to_numeric(row.get("V1.1 Home D1 SOS", row.get("Home SOS")), errors="coerce")
    asos = pd.to_numeric(row.get("V1.1 Away D1 SOS", row.get("Away SOS")), errors="coerce")
    if pd.notna(hsos) and pd.notna(asos):
        diff = float(hsos - asos)
        signed = diff if pick_is_home else -diff
        if signed >= 3:
            positives.append(f"D-I schedule strength is materially stronger for {pick} ({signed:+.1f} differential).")
        elif signed <= -3:
            risks.append(f"The opponent carries the stronger D-I schedule profile ({signed:+.1f} from the pick's perspective).")

    hmatch = pd.to_numeric(row.get("Home Matchup Adj /100"), errors="coerce")
    amatch = pd.to_numeric(row.get("Away Matchup Adj /100"), errors="coerce")
    if pd.notna(hmatch) and pd.notna(amatch):
        diff = float(hmatch - amatch)
        signed = diff if pick_is_home else -diff
        if signed >= 0.75:
            positives.append(f"Four-factor matchup adjustment favors {pick} by about {signed:.1f} points per 100.")
        elif signed <= -0.75:
            risks.append(f"Matchup interaction slightly favors the opponent by about {abs(signed):.1f} per 100.")

    translation = pd.to_numeric(row.get("Schedule Translation Margin Adj"), errors="coerce")
    if pd.notna(translation) and abs(float(translation)) >= 1:
        direction_team = home if float(translation) > 0 else away
        if direction_team == pick:
            positives.append(f"V1.1 cross-schedule translation adds {abs(float(translation)):.1f} margin points toward {pick}.")
        else:
            risks.append(f"V1.1 schedule translation moves {abs(float(translation)):.1f} points against the final model pick.")

    p = pd.to_numeric(row.get("Win Probability"), errors="coerce")
    if pd.notna(p) and float(p) < 0.58:
        risks.append("The game remains inside the model's ambiguity zone (<58% win probability).")
    quality = pd.to_numeric(row.get("Data Quality"), errors="coerce")
    if pd.notna(quality) and float(quality) < 55:
        risks.append(f"Data Quality is only {float(quality):.0f}/100.")
    if not bool(row.get("Availability Verified", False)):
        risks.append("Player availability is not explicitly verified for both teams.")
    if bool(row.get("_pick_changed", False)):
        risks.append("V1.1 changes the winner relative to the frozen V1.0.1 baseline; treat as a high-information challenger case.")
    p10 = pd.to_numeric(row.get("Home Margin P10"), errors="coerce")
    p90 = pd.to_numeric(row.get("Home Margin P90"), errors="coerce")
    if pd.notna(p10) and pd.notna(p90) and float(p10) <= 0 <= float(p90):
        risks.append("The central simulation interval crosses zero, so both teams retain meaningful win paths.")

    if not positives:
        positives.append("The pick is driven by the model's combined opponent-adjusted efficiency, pace, matchup and simulation layers rather than one dominant signal.")
    return positives[:4], risks[:4]


def game_card_html(row: pd.Series) -> str:
    home = str(row.get("Home Team") or "Home")
    away = str(row.get("Away Team") or "Away")
    pick = str(row.get("Model Pick") or "")
    rank = int(float(row.get("Rank") or 0)) if pd.notna(row.get("Rank")) else 0
    hp = row.get("Projected Home Score")
    ap = row.get("Projected Away Score")
    prob = row.get("Win Probability")
    fair_spread = row.get("Fair Spread")
    fair_ml = row.get("Fair Moneyline")
    total = row.get("Projected Total")
    pace = row.get("Expected Pace")
    quality = row.get("Data Quality")
    conf = row.get("Confidence Score")
    neutral = bool(row.get("Neutral Site", False))
    d1 = bool(row.get("D1 Evaluation Eligible", False))
    verified = bool(row.get("Availability Verified", False))
    trans = pd.to_numeric(row.get("Schedule Translation Margin Adj"), errors="coerce")
    base_pick = str(row.get("V1.0.1 Baseline Pick") or "")
    base_prob = row.get("V1.0.1 Baseline Win Probability")
    base_spread = row.get("V1.0.1 Baseline Fair Spread")
    changed = bool(row.get("_pick_changed", False))
    cls = confidence_band(row)

    start = row.get("_start_dt")
    if isinstance(start, pd.Timestamp) and pd.notna(start):
        start_text = start.strftime("%b %d • %H:%M UTC")
    else:
        start_text = "Start time unavailable"

    chips = []
    chips.append(f'<span class="chip {"teal" if d1 else "gold"}">{"D-I vs D-I" if d1 else esc(row.get("Game Classification", "Non-primary"))}</span>')
    if neutral:
        chips.append('<span class="chip orange">Neutral court</span>')
    chips.append(f'<span class="chip {"green" if verified else "gold"}">{"Availability verified" if verified else "Availability unverified"}</span>')
    if pd.notna(trans) and abs(float(trans)) >= .05:
        chips.append(f'<span class="chip orange">Translation {esc(translation_direction(row))}</span>')
    if changed:
        chips.append('<span class="chip red">Baseline pick changed</span>')

    def team_row(name: str, score: Any) -> str:
        tag = '<span class="team-tag">MODEL PICK</span>' if name == pick else ""
        return f'<div class="team-row {"pick" if name == pick else ""}"><div class="team-name">{esc(name)}{tag}</div><div class="score">{fmt_num(score,1)}</div></div>'

    return f"""
    <div class="game-card {cls}">
      <div class="game-head">
        <div>
          <span class="rank-pill">#{rank}</span>
          <div class="game-time">{esc(start_text)} · {"Neutral" if neutral else "Campus/site game"}</div>
        </div>
        <div>
          <div class="prob">{fmt_pct(prob)}</div>
          <div class="prob-label">Model win probability</div>
          <div class="model-pick">{esc(pick)} {fmt_spread(fair_spread)}</div>
        </div>
      </div>
      <div class="scoreboard">
        {team_row(away, ap)}
        {team_row(home, hp)}
      </div>
      <div class="chip-row">{''.join(chips)}</div>
      <div class="card-grid">
        <div class="card-stat"><div class="card-stat-label">Fair ML</div><div class="card-stat-value">{fmt_odds(fair_ml)}</div></div>
        <div class="card-stat"><div class="card-stat-label">Projected total</div><div class="card-stat-value">{fmt_num(total,1)}</div></div>
        <div class="card-stat"><div class="card-stat-label">Expected pace</div><div class="card-stat-value">{fmt_num(pace,1)}</div></div>
        <div class="card-stat"><div class="card-stat-label">Confidence</div><div class="card-stat-value">{fmt_num(conf,0)}/100</div></div>
        <div class="card-stat"><div class="card-stat-label">Data quality</div><div class="card-stat-value">{fmt_num(quality,0)}/100</div></div>
        <div class="card-stat"><div class="card-stat-label">Margin SD</div><div class="card-stat-value">{fmt_num(row.get('Margin SD'),1)}</div></div>
        <div class="card-stat"><div class="card-stat-label">Home AdjNet</div><div class="card-stat-value">{fmt_num(row.get('Home AdjNet'),1)}</div></div>
        <div class="card-stat"><div class="card-stat-label">Away AdjNet</div><div class="card-stat-value">{fmt_num(row.get('Away AdjNet'),1)}</div></div>
      </div>
      <div class="baseline-strip"><strong>Frozen V1.0.1:</strong> {esc(base_pick)} {fmt_spread(base_spread)} · {fmt_pct(base_prob)}. <span class="translation-note">V1.1 translation: {esc(translation_direction(row))}.</span></div>
    </div>
    """


def game_card_grid_html(frame: pd.DataFrame) -> str:
    return '<div class="game-card-grid">' + ''.join(game_card_html(row) for _, row in frame.iterrows()) + '</div>'


def evidence_html(row: pd.Series) -> str:
    positives, risks = signal_readout(row)
    def lis(items: list[str]) -> str:
        return ''.join(f"<li>{esc(x)}</li>" for x in items)
    return f"""
    <div class="evidence-grid">
      <div class="evidence-box positive"><div class="evidence-title">Supporting signals</div><ul class="evidence-list">{lis(positives)}</ul></div>
      <div class="evidence-box risk"><div class="evidence-title">Risks / uncertainty</div><ul class="evidence-list">{lis(risks)}</ul></div>
    </div>
    """
