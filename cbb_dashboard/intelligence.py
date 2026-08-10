from __future__ import annotations

import textwrap
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .ui import esc, fmt_num, fmt_odds, fmt_pct, fmt_spread


DECISION_HOME_SPREAD_COLUMNS = (
    "Bet Home Spread",
    "Taken Home Spread",
    "Decision Home Spread",
    "Market Home Spread",
    "Sportsbook Home Spread",
)
CLOSING_HOME_SPREAD_COLUMNS = ("Closing Home Spread",)


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


def projection_tier(row: pd.Series) -> str:
    p = _num(row, "Win Probability")
    if not np.isfinite(p):
        return "Projection unavailable"
    if p >= 0.70:
        return "Clear model favorite"
    if p >= 0.58:
        return "Model favorite"
    return "Near coin flip"


def model_role(row: pd.Series) -> str:
    version = str(row.get("Model Version") or "").upper()
    if version == "1.1.3B":
        return "Production champion"
    if version == "1.1.3E":
        return "Research challenger"
    return "Historical board"


def calibration_direction(row: pd.Series) -> str:
    """Backward-compatible diagnostic helper.

    Kept for archived tests/admin diagnostics, but no longer displayed on the
    bettor-facing cards in v1.3.
    """
    adj = _num(row, "Champion Margin Calibration Adj", "V1.1.3B Margin Adjustment")
    if not np.isfinite(adj):
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
    return calibration_direction(row)


def _team_prefix(row: pd.Series, team: str) -> str:
    return "Home" if team == str(row.get("Home Team") or "") else "Away"


def _team_value(row: pd.Series, team: str, suffix: str) -> float:
    return _num(row, f"{_team_prefix(row, team)} {suffix}")


def _sos_value(row: pd.Series, team: str) -> float:
    prefix = _team_prefix(row, team)
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


def _pick_context(row: pd.Series) -> tuple[str, str, str, str]:
    pick = str(row.get("Model Pick") or "")
    home = str(row.get("Home Team") or "")
    away = str(row.get("Away Team") or "")
    opponent = away if pick == home else home
    return pick, opponent, _team_prefix(row, pick), _team_prefix(row, opponent)


def pick_margin_interval(row: pd.Series) -> tuple[float, float]:
    """Return P10/P90 margin from the model-pick perspective."""
    p10 = _num(row, "Home Margin P10")
    p90 = _num(row, "Home Margin P90")
    if not (np.isfinite(p10) and np.isfinite(p90)):
        return float("nan"), float("nan")
    pick = str(row.get("Model Pick") or "")
    home = str(row.get("Home Team") or "")
    if pick == home:
        return min(p10, p90), max(p10, p90)
    return min(-p90, -p10), max(-p90, -p10)


def outcome_band_label(row: pd.Series) -> str:
    low, high = pick_margin_interval(row)
    if not (np.isfinite(low) and np.isfinite(high)):
        return "Outcome band unavailable"
    if low > 0:
        return "Pick-positive P10–P90 band"
    if high < 0:
        return "Simulation band conflicts with pick"
    return "Two-way P10–P90 band"


def _first_row_numeric(row: pd.Series, names: Iterable[str]) -> tuple[float, str | None]:
    for name in names:
        if name in row.index:
            value = pd.to_numeric(row.get(name), errors="coerce")
            if pd.notna(value):
                return float(value), name
    return float("nan"), None


def decision_home_spread(row: pd.Series) -> tuple[float, str | None]:
    internal = _num(row, "_market_home_spread")
    if np.isfinite(internal):
        source = str(row.get("_spread_source") or "Decision/market line")
        return internal, source
    return _first_row_numeric(row, DECISION_HOME_SPREAD_COLUMNS)


def closing_home_spread(row: pd.Series) -> tuple[float, str | None]:
    internal = _num(row, "_closing_home_spread")
    if np.isfinite(internal):
        source = str(row.get("_closing_source") or "Closing Home Spread")
        return internal, source
    return _first_row_numeric(row, CLOSING_HOME_SPREAD_COLUMNS)


def selected_team_spread(row: pd.Series, home_spread: float) -> float:
    if not np.isfinite(home_spread):
        return float("nan")
    pick = str(row.get("Model Pick") or "")
    home = str(row.get("Home Team") or "")
    return home_spread if pick == home else -home_spread


def model_market_gap(row: pd.Series) -> float:
    home_line, _ = decision_home_spread(row)
    selected_line = selected_team_spread(row, home_line)
    fair = _num(row, "Fair Spread")
    if not (np.isfinite(selected_line) and np.isfinite(fair)):
        return float("nan")
    # Positive means the stored decision/market line is more favorable to the
    # model-selected side than the model's own fair line.
    return selected_line - fair


def clv_points(row: pd.Series) -> float:
    decision, _ = decision_home_spread(row)
    close, _ = closing_home_spread(row)
    d = selected_team_spread(row, decision)
    c = selected_team_spread(row, close)
    if not (np.isfinite(d) and np.isfinite(c)):
        return float("nan")
    # Positive means the selected side received a better number than the close.
    return d - c


def signal_readout(row: pd.Series) -> tuple[list[str], list[str]]:
    positives: list[str] = []
    risks: list[str] = []
    pick, opponent, _, _ = _pick_context(row)
    home = str(row.get("Home Team") or "")
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
    pick_d = _team_value(row, pick, "AdjD")
    opp_o = _team_value(row, opponent, "AdjO")
    opp_d = _team_value(row, opponent, "AdjD")
    if np.isfinite(pick_o):
        if pick_o >= 116:
            positives.append(f"{pick} brings a high-end adjusted offense ({pick_o:.1f}/100).")
    if np.isfinite(pick_d) and pick_d <= 99:
        positives.append(f"{pick}'s adjusted defense is strong ({pick_d:.1f} allowed/100; lower is better).")
    if np.isfinite(opp_d):
        if opp_d >= 108:
            positives.append(f"{opponent}'s adjusted defense has been permissive ({opp_d:.1f} allowed/100).")
        elif opp_d <= 98:
            risks.append(f"{opponent} owns a strong adjusted defense ({opp_d:.1f} allowed/100).")
    if np.isfinite(opp_o) and opp_o >= 116:
        risks.append(f"{opponent} carries a high-end adjusted offense ({opp_o:.1f}/100).")

    pick_sos = _sos_value(row, pick)
    opp_sos = _sos_value(row, opponent)
    if np.isfinite(pick_sos) and np.isfinite(opp_sos):
        signed = pick_sos - opp_sos
        if signed >= 3:
            positives.append(f"{pick} has faced the materially stronger D-I schedule ({signed:+.1f} SOS gap).")
        elif signed <= -3:
            risks.append(f"{opponent} owns the stronger D-I schedule profile ({abs(signed):.1f} SOS gap).")

    hmatch = _num(row, "Home Matchup Adj /100")
    amatch = _num(row, "Away Matchup Adj /100")
    if np.isfinite(hmatch) and np.isfinite(amatch):
        signed = (hmatch - amatch) if pick_is_home else (amatch - hmatch)
        if signed >= 0.75:
            positives.append(f"The published matchup interaction favors {pick} by about {signed:.1f} points per 100.")
        elif signed <= -0.75:
            risks.append(f"The matchup interaction favors {opponent} by about {abs(signed):.1f} points per 100.")

    p = _num(row, "Win Probability")
    if np.isfinite(p) and p < 0.58:
        risks.append("The matchup remains near a coin flip (<58% model win probability).")
    quality = _num(row, "Data Quality")
    if np.isfinite(quality) and quality < 55:
        risks.append(f"Data Quality is only {quality:.0f}/100.")
    if not _bool(row.get("Availability Verified", False)):
        risks.append("Player availability is not explicitly verified for both teams.")

    low, high = pick_margin_interval(row)
    if np.isfinite(low) and np.isfinite(high) and low <= 0 <= high:
        risks.append("The P10–P90 margin band crosses zero, so both teams retain meaningful win paths.")

    if not positives:
        positives.append("The pick is supported by the combined opponent-adjusted efficiency, matchup, pace and simulation layers rather than one dominant signal.")
    if not risks:
        risks.append("No major structural warning is visible in the published pregame data, but single-game variance remains material.")
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
    winner_count = int(ml is True) + int(spread is True)
    state = "sweep" if winner_count == 2 else ("win" if winner_count == 1 else "loss")
    mark = "W" if winner_count >= 1 else "L"
    score_text = f"FINAL {fa:.0f}-{fh:.0f}" if np.isfinite(fa) and np.isfinite(fh) else "FINAL"

    def pill(label: str, result: Any, css_win: str) -> str:
        if result is True:
            return f'<span class="result-pill {css_win}">{esc(label)} <strong>W</strong></span>'
        if result is False:
            return f'<span class="result-pill loss-pill">{esc(label)} L</span>'
        return f'<span class="result-pill pending-pill">{esc(label)} —</span>'

    decision, _ = decision_home_spread(row)
    close, _ = closing_home_spread(row)
    pick = str(row.get("Model Pick") or "Model pick")
    pick_decision = selected_team_spread(row, decision)
    pick_close = selected_team_spread(row, close)
    clv = clv_points(row)
    explicit_source = str(row.get("_spread_source") or "")

    if np.isfinite(pick_decision):
        line_text = f"ATS line: {pick} {pick_decision:+.1f}"
        if np.isfinite(pick_close):
            line_text += f" · close {pick_close:+.1f}"
            if np.isfinite(clv):
                line_text += f" · CLV {clv:+.1f} pts"
    elif spread is not None and explicit_source:
        line_text = f"ATS result supplied by grader ({explicit_source})"
    elif np.isfinite(pick_close):
        line_text = f"Close {pick_close:+.1f} stored for reference only · ATS requires a decision/taken line"
    else:
        line_text = "ATS not graded — no decision-time/taken spread is stored"

    headline = "ML + ATS SWEEP" if state == "sweep" else ("WINNING RESULT" if state == "win" else "FINAL RESULT")
    return compact_html(f"""
      <div class="result-banner {state}">
        <div class="result-mark">{mark}</div>
        <div class="result-copy"><div class="result-headline">{esc(headline)}</div><div class="result-final">{esc(score_text)}</div></div>
        <div class="result-outcomes">{pill('ML', ml, 'ml-win')}{pill('ATS', spread, 'spread-win')}</div>
        <div class="result-line">{esc(line_text)}</div>
      </div>
    """)


def _fmt(value: float, digits: int = 1, suffix: str = "") -> str:
    return fmt_num(value, digits, suffix) if np.isfinite(value) else "—"


def _profile_metric(label: str, value: object, note: str = "") -> str:
    note_html = f'<span class="profile-note">{esc(note)}</span>' if note else ""
    return f'<div class="profile-metric"><span>{esc(label)}</span><strong>{esc(value)}</strong>{note_html}</div>'


def _team_profile_card(row: pd.Series, team: str, focus_team: str) -> str:
    prefix = _team_prefix(row, team)
    is_pick = team == str(row.get("Model Pick") or "")
    is_focus = team == focus_team
    role = "MODEL PICK" if is_pick else ("FOCUS TEAM" if is_focus else "OPPONENT")
    ppg = _ppg(row, prefix)
    ppga = _ppga(row, prefix)
    metrics = "".join([
        _profile_metric("AdjO", _fmt(_num(row, f"{prefix} AdjO"))),
        _profile_metric("AdjD", _fmt(_num(row, f"{prefix} AdjD")), "lower better"),
        _profile_metric("AdjNet", _fmt(_num(row, f"{prefix} AdjNet"))),
        _profile_metric("D-I SOS", _fmt(_sos_value(row, team))),
        _profile_metric("PPG", _fmt(ppg)),
        _profile_metric("PPG allowed", _fmt(ppga)),
        _profile_metric("Matchup /100", _fmt(_num(row, f"{prefix} Matchup Adj /100"))),
        _profile_metric("Availability adj", _fmt(_num(row, f"{prefix} Availability Adj"), 1, " pts")),
    ])
    classes = "team-profile-card"
    if is_focus:
        classes += " focus"
    if is_pick:
        classes += " selected"
    return compact_html(f"""
      <div class="{classes}">
        <div class="team-profile-head"><div><span>{esc(role)}</span><strong>{esc(team)}</strong></div>{'<span class="pick-check">✓</span>' if is_pick else ''}</div>
        <div class="team-profile-metrics">{metrics}</div>
      </div>
    """)


def team_profile_pair_html(row: pd.Series, focus_team: str | None = None) -> str:
    home = str(row.get("Home Team") or "")
    away = str(row.get("Away Team") or "")
    pick = str(row.get("Model Pick") or "")
    focus = focus_team if focus_team in {home, away} else pick
    other = away if focus == home else home
    cards = _team_profile_card(row, focus, focus) + _team_profile_card(row, other, focus)
    has_ppg = np.isfinite(_ppg(row, _team_prefix(row, focus))) and np.isfinite(_ppg(row, _team_prefix(row, other)))
    foot = "" if has_ppg else '<div class="dossier-footnote">PPG / PPG allowed appear only when true pregame descriptive fields are published; the site never derives them from projected scores.</div>'
    return compact_html(f'<div class="team-profile-grid">{cards}</div>{foot}')


def team_snapshot_html(row: pd.Series) -> str:
    return team_profile_pair_html(row, str(row.get("Model Pick") or ""))


def matchup_battle_html(row: pd.Series, focus_team: str | None = None) -> str:
    home = str(row.get("Home Team") or "")
    away = str(row.get("Away Team") or "")
    pick = str(row.get("Model Pick") or "")
    focus = focus_team if focus_team in {home, away} else pick
    other = away if focus == home else home
    focus_o = _team_value(row, focus, "AdjO")
    focus_d = _team_value(row, focus, "AdjD")
    other_o = _team_value(row, other, "AdjO")
    other_d = _team_value(row, other, "AdjD")
    net_gap = _team_value(row, focus, "AdjNet") - _team_value(row, other, "AdjNet")
    sos_gap = _sos_value(row, focus) - _sos_value(row, other)
    return compact_html(f"""
      <div class="battle-shell">
        <div class="battle-title">MATCHUP BATTLEGROUND</div>
        <div class="battle-grid">
          <div class="battle-card"><span>{esc(focus)} offense</span><strong>{_fmt(focus_o)}</strong><em>AdjO vs {esc(other)} AdjD {_fmt(other_d)}</em></div>
          <div class="battle-card"><span>{esc(other)} offense</span><strong>{_fmt(other_o)}</strong><em>AdjO vs {esc(focus)} AdjD {_fmt(focus_d)}</em></div>
          <div class="battle-card"><span>AdjNet gap</span><strong>{_fmt(net_gap,1,' pts')}</strong><em>positive favors {esc(focus)}</em></div>
          <div class="battle-card"><span>SOS gap</span><strong>{_fmt(sos_gap,1)}</strong><em>positive = tougher {esc(focus)} schedule</em></div>
        </div>
      </div>
    """)


def evidence_html(row: pd.Series) -> str:
    positives, risks = signal_readout(row)

    def lis(items: Iterable[str]) -> str:
        return "".join(f"<li>{esc(x)}</li>" for x in items)

    pick = str(row.get("Model Pick") or "the pick")
    return compact_html(f"""
      <div class="evidence-grid">
        <div class="evidence-box positive"><div class="evidence-title">WHY THE MODEL LIKES {esc(pick)}</div><ul class="evidence-list">{lis(positives)}</ul></div>
        <div class="evidence-box risk"><div class="evidence-title">WHAT CAN BEAT THE PICK</div><ul class="evidence-list">{lis(risks)}</ul></div>
      </div>
    """)


def market_context_html(row: pd.Series) -> str:
    decision, decision_source = decision_home_spread(row)
    close, _ = closing_home_spread(row)
    pick = str(row.get("Model Pick") or "Model pick")
    selected_decision = selected_team_spread(row, decision)
    selected_close = selected_team_spread(row, close)
    gap = model_market_gap(row)
    clv = clv_points(row)

    if not np.isfinite(selected_decision):
        close_note = f' Closing line {selected_close:+.1f} is stored for reference only.' if np.isfinite(selected_close) else ""
        return compact_html(f"""
          <div class="market-context neutral">
            <div><span>MARKET CONTEXT</span><strong>No decision-time spread stored</strong></div>
            <p>The model forecast remains market-blind.{esc(close_note)} No ATS recommendation is inferred from the model line alone.</p>
          </div>
        """)

    gap_text = f"{gap:+.1f} pts vs model fair" if np.isfinite(gap) else "Model gap unavailable"
    close_html = ""
    if np.isfinite(selected_close):
        clv_text = f" · CLV {clv:+.1f} pts" if np.isfinite(clv) else ""
        close_html = f'<span class="market-close">Close {selected_close:+.1f}{clv_text}</span>'
    return compact_html(f"""
      <div class="market-context live">
        <div><span>MARKET CONTEXT</span><strong>{esc(pick)} {selected_decision:+.1f}</strong></div>
        <div class="market-gap">{esc(gap_text)}</div>{close_html}
        <p>Display-only market comparison. It does not feed the production model and is not an automatic bet/EV label. Source: {esc(decision_source or 'published line')}.</p>
      </div>
    """)


def betting_snapshot_html(row: pd.Series) -> str:
    low, high = pick_margin_interval(row)
    interval = f"{low:+.1f} to {high:+.1f}" if np.isfinite(low) and np.isfinite(high) else "—"
    metrics = "".join([
        _profile_metric("Model line", fmt_spread(row.get("Fair Spread"))),
        _profile_metric("Model fair ML", fmt_odds(row.get("Fair Moneyline"))),
        _profile_metric("Projected total", fmt_num(row.get("Projected Total"), 1)),
        _profile_metric("Expected pace", fmt_num(row.get("Expected Pace"), 1)),
        _profile_metric("Pick margin P10–P90", interval),
        _profile_metric("Data quality", f"{fmt_num(row.get('Data Quality'),0)}/100"),
    ])
    return compact_html(f'<div class="betting-snapshot">{metrics}</div>')


def dossier_html(row: pd.Series) -> str:
    low, high = pick_margin_interval(row)
    interval = f"{low:+.1f} / {high:+.1f}" if np.isfinite(low) and np.isfinite(high) else "—"
    availability = "Verified" if _bool(row.get("Availability Verified", False)) else "Unverified"
    site = "Neutral court" if _bool(row.get("Neutral Site", False)) else "Campus/site game"
    context = compact_html(f"""
      <div class="dossier-context-grid">
        <div class="dossier-context"><span>Projection tier</span><strong>{esc(projection_tier(row))}</strong></div>
        <div class="dossier-context"><span>Pick margin P10/P90</span><strong>{esc(interval)}</strong></div>
        <div class="dossier-context"><span>Margin SD</span><strong>{fmt_num(row.get('Margin SD'),1)}</strong></div>
        <div class="dossier-context"><span>Availability</span><strong>{esc(availability)}</strong></div>
        <div class="dossier-context"><span>Game site</span><strong>{esc(site)}</strong></div>
        <div class="dossier-context"><span>Data quality</span><strong>{fmt_num(row.get('Data Quality'),0)}/100</strong></div>
      </div>
    """)
    return compact_html(f"""
      <details class="intel-dossier">
        <summary><span>Game Intelligence Dossier</span><span>Thesis / risk / team profiles / market context ＋</span></summary>
        <div class="dossier-body">{evidence_html(row)}{team_snapshot_html(row)}{matchup_battle_html(row)}{market_context_html(row)}{context}</div>
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
    cls = confidence_band(row)

    start = row.get("_start_dt")
    if isinstance(start, pd.Timestamp) and pd.notna(start):
        start_text = start.strftime("%b %d • %H:%M UTC")
    else:
        start_text = "Start time unavailable"

    chips = [
        f'<span class="chip {"teal" if d1 else "gold"}">{"D-I vs D-I" if d1 else esc(row.get("Game Classification", "Non-primary"))}</span>',
        f'<span class="chip projection">{esc(projection_tier(row))}</span>',
    ]
    if neutral:
        chips.append('<span class="chip orange">Neutral court</span>')
    chips.append(f'<span class="chip {"green" if verified else "gold"}">{"Availability verified" if verified else "Availability unverified"}</span>')
    chips.append(f'<span class="chip champion">{esc(model_role(row))}</span>')
    band = outcome_band_label(row)
    chips.append(f'<span class="chip {"green" if band.startswith("Pick-positive") else "gold"}">{esc(band)}</span>')

    decision, _ = decision_home_spread(row)
    selected_decision = selected_team_spread(row, decision)
    gap = model_market_gap(row)
    if np.isfinite(selected_decision):
        gap_text = f" · gap {gap:+.1f}" if np.isfinite(gap) else ""
        chips.append(f'<span class="chip market">Market {selected_decision:+.1f}{esc(gap_text)}</span>')

    def team_row(name: str, score: Any) -> str:
        tag = '<span class="team-tag">MODEL PICK</span>' if name == pick else ""
        return f'<div class="team-row {"pick" if name == pick else ""}"><div class="team-name">{esc(name)}{tag}</div><div class="score">{fmt_num(score,1)}</div></div>'

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
        {betting_snapshot_html(row)}
        {dossier_html(row)}
      </div>
    """)


def game_card_grid_html(frame: pd.DataFrame) -> str:
    cards = "".join(game_card_html(row) for _, row in frame.iterrows())
    return compact_html(f'<div class="game-card-grid">{cards}</div>')
