from __future__ import annotations

import textwrap
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .ui import esc, fmt_num, fmt_odds, fmt_pct, fmt_spread


def compact_html(value: str) -> str:
    """Return Streamlit-safe inline HTML.

    Markdown interprets lines indented four spaces as code blocks even when
    unsafe_allow_html=True. Keeping generated card markup on a single logical
    line prevents later cards from being rendered as visible source code.
    """
    dedented = textwrap.dedent(value or "").strip()
    return " ".join(line.strip() for line in dedented.splitlines() if line.strip())


def _num(row: pd.Series, *names: str) -> float:
    for name in names:
        if name in row.index:
            value = pd.to_numeric(row.get(name), errors="coerce")
            if pd.notna(value):
                return float(value)
    return float("nan")


def _bool(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return False
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "w", "win"}:
        return True
    if text in {"false", "0", "no", "n", "l", "loss"}:
        return False
    return bool(value)


def confidence_band(row: pd.Series) -> str:
    p = _num(row, "Win Probability")
    p = p if np.isfinite(p) else 0.5
    if p >= 0.75:
        return "strong"
    if p < 0.58:
        return "tossup"
    return "standard"


def model_role(row: pd.Series) -> str:
    version = str(row.get("Model Version") or "")
    if version.upper() == "1.1.3B":
        return "Production champion"
    if version.upper() == "1.1.3E":
        return "Research challenger"
    return "Historical 1.1.x"


def calibration_direction(row: pd.Series) -> str:
    adj = _num(row, "Champion Margin Calibration Adj", "V1.1.3B Margin Adjustment")
    if not np.isfinite(adj):
        # Backward-compatible archive rendering for old V1.1.x slates.
        adj = _num(row, "Schedule Translation Margin Adj")
        if not np.isfinite(adj) or abs(adj) < 0.05:
            return "No material margin calibration"
        team = row.get("Home Team") if adj > 0 else row.get("Away Team")
        return f"Historical adjustment {abs(adj):.1f} pts toward {team}"
    if abs(adj) < 0.05:
        return "No material B calibration"
    team = row.get("Home Team") if adj > 0 else row.get("Away Team")
    return f"B calibration {abs(adj):.1f} pts toward {team}"


def translation_direction(row: pd.Series) -> str:
    """Backward-compatible alias used by archived v1.1 UI/tests."""
    return calibration_direction(row)


def _team_value(row: pd.Series, team: str, suffix: str) -> float:
    home = str(row.get("Home Team") or "")
    prefix = "Home" if team == home else "Away"
    return _num(row, f"{prefix} {suffix}")


def _sos_value(row: pd.Series, team: str) -> float:
    home = str(row.get("Home Team") or "")
    prefix = "Home" if team == home else "Away"
    return _num(row, f"V1.1 {prefix} D1 SOS", f"{prefix} D1 SOS", f"{prefix} SOS")


def _ppg(row: pd.Series, prefix: str) -> float:
    return _num(
        row,
        f"{prefix} PPG",
        f"{prefix} Points Per Game",
        f"{prefix} Avg Points",
        f"{prefix} Scoring PPG",
    )


def _ppga(row: pd.Series, prefix: str) -> float:
    return _num(
        row,
        f"{prefix} PPG Allowed",
        f"{prefix} Points Allowed Per Game",
        f"{prefix} Avg Points Allowed",
        f"{prefix} Defensive PPG",
    )


def signal_readout(row: pd.Series) -> tuple[list[str], list[str]]:
    positives: list[str] = []
    risks: list[str] = []
    pick = str(row.get("Model Pick") or "")
    home = str(row.get("Home Team") or "")
    away = str(row.get("Away Team") or "")
    opponent = away if pick == home else home
    pick_is_home = pick == home

    home_net = _num(row, "Home AdjNet")
    away_net = _num(row, "Away AdjNet")
    if np.isfinite(home_net) and np.isfinite(away_net):
        diff = home_net - away_net
        signed = diff if pick_is_home else -diff
        if signed >= 3:
            positives.append(f"Adjusted net efficiency favors {pick} by {signed:.1f} points per 100 possessions.")
        elif signed <= -3:
            risks.append(f"Adjusted net efficiency favors {opponent} by {abs(signed):.1f} points per 100 possessions.")

    pick_o = _team_value(row, pick, "AdjO")
    opp_d = _team_value(row, opponent, "AdjD")
    if np.isfinite(pick_o) and np.isfinite(opp_d):
        if pick_o >= 116:
            positives.append(f"{pick} brings a high-end adjusted offense ({pick_o:.1f}/100) into this matchup.")
        if opp_d >= 108:
            positives.append(f"{opponent}'s adjusted defense has been permissive ({opp_d:.1f} allowed/100).")
        elif opp_d <= 98:
            risks.append(f"{opponent} owns a strong adjusted defense ({opp_d:.1f} allowed/100).")

    hsos = _sos_value(row, home)
    asos = _sos_value(row, away)
    if np.isfinite(hsos) and np.isfinite(asos):
        diff = hsos - asos
        signed = diff if pick_is_home else -diff
        if signed >= 3:
            positives.append(f"The pick has faced the materially stronger D-I schedule ({signed:+.1f} SOS differential).")
        elif signed <= -3:
            risks.append(f"The opponent owns the stronger D-I schedule profile ({signed:+.1f} from the pick's perspective).")

    hmatch = _num(row, "Home Matchup Adj /100")
    amatch = _num(row, "Away Matchup Adj /100")
    if np.isfinite(hmatch) and np.isfinite(amatch):
        diff = hmatch - amatch
        signed = diff if pick_is_home else -diff
        if signed >= 0.75:
            positives.append(f"Four-factor matchup interaction favors {pick} by about {signed:.1f} points per 100.")
        elif signed <= -0.75:
            risks.append(f"Four-factor matchup interaction favors {opponent} by about {abs(signed):.1f} points per 100.")

    cal = _num(row, "Champion Margin Calibration Adj", "V1.1.3B Margin Adjustment")
    if np.isfinite(cal) and abs(cal) >= 0.75:
        direction_team = home if cal > 0 else away
        if direction_team == pick:
            positives.append(f"Frozen B calibration adds {abs(cal):.1f} margin points toward {pick} based only on prior graded history.")
        else:
            risks.append(f"B calibration trims the pick by {abs(cal):.1f} margin points relative to the frozen V1.0.1 anchor.")
    if np.isfinite(cal) and abs(cal) >= 3.0:
        risks.append("The margin requires a relatively large calibration move; treat the point estimate as less stable than the side itself.")

    p = _num(row, "Win Probability")
    if np.isfinite(p) and p < 0.58:
        risks.append("The matchup remains inside the model's ambiguity zone (<58% win probability).")
    quality = _num(row, "Data Quality")
    if np.isfinite(quality) and quality < 55:
        risks.append(f"Data Quality is only {quality:.0f}/100.")
    if not _bool(row.get("Availability Verified", False)):
        risks.append("Player availability is not explicitly verified for both teams.")
    if _bool(row.get("_pick_changed", False)):
        risks.append("This historical 1.1.x board changes the winner relative to the frozen V1.0.1 anchor; treat it as a high-information model-change case.")
    p10 = _num(row, "Home Margin P10")
    p90 = _num(row, "Home Margin P90")
    if np.isfinite(p10) and np.isfinite(p90) and p10 <= 0 <= p90:
        risks.append("The central simulation interval crosses zero, so both teams retain meaningful win paths.")

    if not positives:
        positives.append("The pick comes from the combined opponent-adjusted efficiency, matchup, pace and simulation layers rather than one dominant signal.")
    if not risks:
        risks.append("No major structural warning is visible in the published board, but single-game variance remains high.")
    return positives[:5], risks[:5]


def _result_banner(row: pd.Series) -> str:
    if not _bool(row.get("_grade_eligible", False)):
        return ""
    fa = _num(row, "_final_away", "Final Away Score")
    fh = _num(row, "_final_home", "Final Home Score")
    def outcome(value: Any) -> bool | None:
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        return bool(value)

    ml = outcome(row.get("_ml_correct"))
    spread = outcome(row.get("_spread_correct"))
    line = _num(row, "_market_home_spread")
    winner_count = int(ml is True) + int(spread is True)
    state = "sweep" if winner_count == 2 else ("win" if winner_count == 1 else "loss")
    score_text = f"FINAL {fa:.0f}-{fh:.0f}" if np.isfinite(fa) and np.isfinite(fh) else "FINAL"

    def pill(label: str, outcome: Any, css_win: str) -> str:
        if outcome is True:
            return f'<span class="result-pill {css_win}">{esc(label)} <strong>W</strong></span>'
        if outcome is False:
            return f'<span class="result-pill loss-pill">{esc(label)} L</span>'
        return f'<span class="result-pill pending-pill">{esc(label)} —</span>'

    line_text = f"Home line {line:+.1f}" if np.isfinite(line) else "Spread grade requires published market line"
    return compact_html(f"""
      <div class="result-banner {state}">
        <div class="result-final">{esc(score_text)}</div>
        <div class="result-outcomes">{pill('ML', ml, 'ml-win')}{pill('SPREAD', spread, 'spread-win')}</div>
        <div class="result-line">{esc(line_text)}</div>
      </div>
    """)


def _intel_row(label: str, left: object, right: object) -> str:
    return (
        '<div class="matchup-row">'
        f'<span class="matchup-label">{esc(label)}</span>'
        f'<span class="matchup-value pick-side">{esc(left)}</span>'
        f'<span class="matchup-value opp-side">{esc(right)}</span>'
        '</div>'
    )


def _fmt(value: float, digits: int = 1, suffix: str = "") -> str:
    return fmt_num(value, digits, suffix) if np.isfinite(value) else "—"


def team_snapshot_html(row: pd.Series) -> str:
    pick = str(row.get("Model Pick") or "")
    home = str(row.get("Home Team") or "")
    away = str(row.get("Away Team") or "")
    opponent = away if pick == home else home
    pick_prefix = "Home" if pick == home else "Away"
    opp_prefix = "Away" if pick == home else "Home"

    rows = "".join([
        _intel_row("AdjO", _fmt(_num(row, f"{pick_prefix} AdjO")), _fmt(_num(row, f"{opp_prefix} AdjO"))),
        _intel_row("AdjD (lower better)", _fmt(_num(row, f"{pick_prefix} AdjD")), _fmt(_num(row, f"{opp_prefix} AdjD"))),
        _intel_row("AdjNet", _fmt(_num(row, f"{pick_prefix} AdjNet")), _fmt(_num(row, f"{opp_prefix} AdjNet"))),
        _intel_row("D-I SOS", _fmt(_sos_value(row, pick)), _fmt(_sos_value(row, opponent))),
        _intel_row("PPG", _fmt(_ppg(row, pick_prefix)), _fmt(_ppg(row, opp_prefix))),
        _intel_row("PPG allowed", _fmt(_ppga(row, pick_prefix)), _fmt(_ppga(row, opp_prefix))),
        _intel_row("Matchup adj /100", _fmt(_num(row, f"{pick_prefix} Matchup Adj /100")), _fmt(_num(row, f"{opp_prefix} Matchup Adj /100"))),
        _intel_row("Availability adj", _fmt(_num(row, f"{pick_prefix} Availability Adj"), 1, " pts"), _fmt(_num(row, f"{opp_prefix} Availability Adj"), 1, " pts")),
    ])
    return compact_html(f"""
      <div class="matchup-table">
        <div class="matchup-head"><span>Metric</span><strong>{esc(pick)}</strong><strong>{esc(opponent)}</strong></div>
        {rows}
      </div>
      <div class="dossier-footnote">PPG / PPG allowed display only when those pregame descriptive fields are present in the published board; they are never inferred from projected scores.</div>
    """)


def evidence_html(row: pd.Series) -> str:
    positives, risks = signal_readout(row)

    def lis(items: Iterable[str]) -> str:
        return "".join(f"<li>{esc(x)}</li>" for x in items)

    pick = str(row.get("Model Pick") or "the pick")
    return compact_html(f"""
      <div class="evidence-grid">
        <div class="evidence-box positive"><div class="evidence-title">↑ Why we like {esc(pick)}</div><ul class="evidence-list">{lis(positives)}</ul></div>
        <div class="evidence-box risk"><div class="evidence-title">↓ Risks / reasons for caution</div><ul class="evidence-list">{lis(risks)}</ul></div>
      </div>
    """)


def dossier_html(row: pd.Series) -> str:
    base_home = _num(row, "Champion Baseline Home Margin")
    calibrated_home = _num(row, "Champion Calibrated Home Margin")
    correction = _num(row, "Champion Margin Calibration Adj", "V1.1.3B Margin Adjustment")
    if not np.isfinite(base_home):
        base_home = _num(row, "V1.0.1 Baseline Projected Home Score") - _num(row, "V1.0.1 Baseline Projected Away Score")
    if not np.isfinite(calibrated_home):
        calibrated_home = _num(row, "Projected Home Score") - _num(row, "Projected Away Score")

    context = compact_html(f"""
      <div class="dossier-context-grid">
        <div class="dossier-context"><span>Expected pace</span><strong>{fmt_num(row.get('Expected Pace'),1)}</strong></div>
        <div class="dossier-context"><span>Margin P10/P90</span><strong>{fmt_num(row.get('Home Margin P10'),1)} / {fmt_num(row.get('Home Margin P90'),1)}</strong></div>
        <div class="dossier-context"><span>Baseline home margin</span><strong>{_fmt(base_home)}</strong></div>
        <div class="dossier-context"><span>B calibrated margin</span><strong>{_fmt(calibrated_home)}</strong></div>
        <div class="dossier-context"><span>B adjustment</span><strong>{_fmt(correction,1,' pts')}</strong></div>
        <div class="dossier-context"><span>Data quality</span><strong>{fmt_num(row.get('Data Quality'),0)}/100</strong></div>
      </div>
    """)
    return compact_html(f"""
      <details class="intel-dossier">
        <summary><span>Game Intelligence Dossier</span><span>Why the pick / matchup risks / team profile ＋</span></summary>
        <div class="dossier-body">{evidence_html(row)}{team_snapshot_html(row)}{context}</div>
      </details>
    """)


def game_card_html(row: pd.Series) -> str:
    home = str(row.get("Home Team") or "Home")
    away = str(row.get("Away Team") or "Away")
    pick = str(row.get("Model Pick") or "")
    rank_value = _num(row, "Rank", "_rank")
    rank = int(rank_value) if np.isfinite(rank_value) else 0
    prob = row.get("Win Probability")
    neutral = _bool(row.get("Neutral Site", False))
    d1 = _bool(row.get("D1 Evaluation Eligible", False))
    verified = _bool(row.get("Availability Verified", False))
    base_pick = str(row.get("V1.0.1 Baseline Pick") or "")
    base_prob = row.get("V1.0.1 Baseline Win Probability")
    base_spread = row.get("V1.0.1 Baseline Fair Spread")
    cls = confidence_band(row)

    start = row.get("_start_dt")
    if isinstance(start, pd.Timestamp) and pd.notna(start):
        start_text = start.strftime("%b %d • %H:%M UTC")
    else:
        start_text = "Start time unavailable"

    chips = [
        f'<span class="chip {"teal" if d1 else "gold"}">{"D-I vs D-I" if d1 else esc(row.get("Game Classification", "Non-primary"))}</span>',
    ]
    if neutral:
        chips.append('<span class="chip orange">Neutral court</span>')
    chips.append(f'<span class="chip {"green" if verified else "gold"}">{"Availability verified" if verified else "Availability unverified"}</span>')
    role = model_role(row)
    chips.append(f'<span class="chip champion">{esc(role)}</span>')
    cal = _num(row, "Champion Margin Calibration Adj", "V1.1.3B Margin Adjustment")
    if np.isfinite(cal) and abs(cal) >= 0.05:
        chips.append(f'<span class="chip orange">{esc(calibration_direction(row))}</span>')

    def team_row(name: str, score: Any) -> str:
        tag = '<span class="team-tag">MODEL PICK</span>' if name == pick else ""
        return f'<div class="team-row {"pick" if name == pick else ""}"><div class="team-name">{esc(name)}{tag}</div><div class="score">{fmt_num(score,1)}</div></div>'

    pick_is_home = pick == home
    pick_net = row.get("Home AdjNet" if pick_is_home else "Away AdjNet")
    opp_net = row.get("Away AdjNet" if pick_is_home else "Home AdjNet")
    result = _result_banner(row)

    return compact_html(f"""
      <div class="game-card {cls}">
        {result}
        <div class="game-head">
          <div><span class="rank-pill">#{rank}</span><div class="game-time">{esc(start_text)} · {"Neutral" if neutral else "Campus/site game"}</div></div>
          <div><div class="prob">{fmt_pct(prob)}</div><div class="prob-label">Model win probability</div><div class="model-pick">{esc(pick)} {fmt_spread(row.get('Fair Spread'))}</div></div>
        </div>
        <div class="scoreboard">{team_row(away, row.get('Projected Away Score'))}{team_row(home, row.get('Projected Home Score'))}</div>
        <div class="chip-row">{''.join(chips)}</div>
        <div class="card-grid">
          <div class="card-stat"><div class="card-stat-label">Fair ML</div><div class="card-stat-value">{fmt_odds(row.get('Fair Moneyline'))}</div></div>
          <div class="card-stat"><div class="card-stat-label">Projected total</div><div class="card-stat-value">{fmt_num(row.get('Projected Total'),1)}</div></div>
          <div class="card-stat"><div class="card-stat-label">Expected pace</div><div class="card-stat-value">{fmt_num(row.get('Expected Pace'),1)}</div></div>
          <div class="card-stat"><div class="card-stat-label">Margin SD</div><div class="card-stat-value">{fmt_num(row.get('Margin SD'),1)}</div></div>
          <div class="card-stat"><div class="card-stat-label">Data quality</div><div class="card-stat-value">{fmt_num(row.get('Data Quality'),0)}/100</div></div>
          <div class="card-stat"><div class="card-stat-label">B calibration</div><div class="card-stat-value">{_fmt(cal,1,' pts') if np.isfinite(cal) else 'Archive'}</div></div>
          <div class="card-stat"><div class="card-stat-label">Pick AdjNet</div><div class="card-stat-value">{fmt_num(pick_net,1)}</div></div>
          <div class="card-stat"><div class="card-stat-label">Opp AdjNet</div><div class="card-stat-value">{fmt_num(opp_net,1)}</div></div>
        </div>
        <div class="baseline-strip"><strong>Frozen V1.0.1 audit:</strong> {esc(base_pick)} {fmt_spread(base_spread)} · {fmt_pct(base_prob)}. <span class="translation-note">{esc(calibration_direction(row))}.</span></div>
        {dossier_html(row)}
      </div>
    """)


def game_card_grid_html(frame: pd.DataFrame) -> str:
    cards = "".join(game_card_html(row) for _, row in frame.iterrows())
    return compact_html(f'<div class="game-card-grid">{cards}</div>')
