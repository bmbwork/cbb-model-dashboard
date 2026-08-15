from __future__ import annotations

import textwrap
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .ui import esc, fmt_num, fmt_odds, fmt_pct, fmt_spread
from .market import context_flags, market_features


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
        return "Pick strength unavailable"
    if p >= 0.70:
        return "Strong model favorite"
    if p >= 0.58:
        return "Model favorite"
    return "Close game"

def model_role(row: pd.Series) -> str:
    version = str(row.get("Model Version") or "").upper()
    if version == "1.1.3B":
        return "Production model"
    if version == "1.1.3E":
        return "Research model"
    return "Historical model"

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


def margin_swing_text(row: pd.Series) -> str:
    value = _num(row, "Margin SD")
    if not np.isfinite(value):
        return "—"
    return f"{value:.1f} pts"


def closing_line_edge_text(row: pd.Series) -> str:
    value = clv_points(row)
    if not np.isfinite(value):
        return ""
    if abs(value) < 0.05:
        return "Matched the closing line"
    if value > 0:
        return f"Beat closing line by {value:.1f} pts"
    return f"Worse than closing line by {abs(value):.1f} pts"

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
            positives.append(f"{pick} has the stronger overall team-efficiency profile by {signed:.1f} points.")
        elif signed <= -3:
            risks.append(f"{opponent} has the stronger overall team-efficiency profile by {abs(signed):.1f} points.")

    pick_o = _team_value(row, pick, "AdjO")
    pick_d = _team_value(row, pick, "AdjD")
    opp_o = _team_value(row, opponent, "AdjO")
    opp_d = _team_value(row, opponent, "AdjD")
    if np.isfinite(pick_o) and pick_o >= 116:
        positives.append(f"{pick} rates as a high-end offense after adjusting for opponent strength (offense rating {pick_o:.1f}).")
    if np.isfinite(pick_d) and pick_d <= 99:
        positives.append(f"{pick} rates as a strong defense after adjusting for opponent strength (defense rating {pick_d:.1f}; lower is better).")
    if np.isfinite(opp_d):
        if opp_d >= 108:
            positives.append(f"{opponent}'s defense has been easier to score on than most (defense rating {opp_d:.1f}).")
        elif opp_d <= 98:
            risks.append(f"{opponent} has a strong defense (defense rating {opp_d:.1f}; lower is better).")
    if np.isfinite(opp_o) and opp_o >= 116:
        risks.append(f"{opponent} has a high-end offense (offense rating {opp_o:.1f}).")

    pick_sos = _sos_value(row, pick)
    opp_sos = _sos_value(row, opponent)
    if np.isfinite(pick_sos) and np.isfinite(opp_sos):
        signed = pick_sos - opp_sos
        if signed >= 3:
            positives.append(f"{pick} has played a meaningfully tougher schedule than {opponent} (schedule-strength edge {signed:.1f}).")
        elif signed <= -3:
            risks.append(f"{opponent} has played a meaningfully tougher schedule than {pick} (schedule-strength edge {abs(signed):.1f}).")

    hmatch = _num(row, "Home Matchup Adj /100")
    amatch = _num(row, "Away Matchup Adj /100")
    if np.isfinite(hmatch) and np.isfinite(amatch):
        signed = (hmatch - amatch) if pick_is_home else (amatch - hmatch)
        if signed >= 0.75:
            positives.append(f"The style matchup gives {pick} a small additional edge.")
        elif signed <= -0.75:
            risks.append(f"The style matchup gives {opponent} a small additional edge.")

    p = _num(row, "Win Probability")
    if np.isfinite(p) and p < 0.58:
        risks.append(f"This is a close game: the model gives {pick} less than a 58% chance to win.")
    quality = _num(row, "Data Quality")
    if np.isfinite(quality) and quality < 55:
        risks.append(f"The model inputs are incomplete or lower-confidence for this game ({quality:.0f}/100 data confidence).")
    if not _bool(row.get("Availability Verified", False)):
        risks.append("Player availability has not been fully verified, so late lineup news could change the matchup.")

    # Owner-authorized market context. Only non-numeric, derived commentary is
    # stored on the public row; raw Owls ticket/handle percentages remain private.
    betting_signal = str(row.get("Betting Signal") or "").strip()
    public_side = str(row.get("Betting Public Side") or "").strip()
    money_side = str(row.get("Betting Money Side") or "").strip()
    sharp_side = str(row.get("Betting Sharp Side") or "").strip()
    sharp_signal = str(row.get("Betting Sharp Signal") or "").strip()
    sharp_confidence = str(row.get("Betting Sharp Confidence") or "").strip()

    if sharp_side and sharp_signal in {"sharp_consensus", "sharp_possible"}:
        if pick == sharp_side:
            qualifier = "across multiple sportsbooks" if sharp_signal == "sharp_consensus" else "in the available split data"
            positives.append(f"A sharp-money signal {qualifier} also favors {pick}: the dollar share is heavier than the ticket share on that side. This is market context, not a model input.")
        elif opponent == sharp_side:
            qualifier = "strong" if sharp_confidence in {"strong", "very strong"} else "possible"
            risks.append(f"A {qualifier} sharp-money signal favors {opponent}, which disagrees with the model pick. That does not invalidate the model, but it is meaningful market risk.")
    elif sharp_signal == "sharp_mixed":
        risks.append("Sharp-money reads disagree across sportsbooks, so there is no clean professional-money confirmation for either side.")
    elif betting_signal == "money_disagrees" and public_side and money_side:
        if pick == money_side:
            positives.append(f"Betting-market context also leans toward {pick}: the money side favors the model pick even though more individual bets are on {public_side}.")
        elif pick == public_side:
            risks.append(f"Betting-market context is mixed: more individual bets are on {pick}, but the money side favors {money_side}.")

    if betting_signal == "public_heavy" and public_side:
        if public_side == pick:
            risks.append(f"{pick} is a heavily popular betting side. The model may still be right, but a crowded side can come with a less attractive sportsbook price.")
        elif public_side == opponent:
            risks.append(f"The betting crowd is heavily backing {opponent}, so the model pick is running against a strongly popular market side.")
    elif betting_signal == "public_lean" and public_side and public_side == opponent:
        risks.append(f"The betting crowd leans toward {opponent}, creating a modest model-versus-public disagreement.")

    if not positives:
        positives.append("No single factor dominates. The pick comes from the combined team-strength, matchup, game-speed and simulation picture.")
    if not risks:
        risks.append("No major warning stands out in the available pregame data, but any single college basketball game can still swing sharply.")
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

    def pill(label: str, result: Any, css_win: str, help_text: str) -> str:
        title = esc(help_text)
        if result is True:
            return f'<span class="result-pill {css_win}" title="{title}">{esc(label)} <strong>W</strong></span>'
        if result is False:
            return f'<span class="result-pill loss-pill" title="{title}">{esc(label)} L</span>'
        return f'<span class="result-pill pending-pill" title="{title}">{esc(label)} —</span>'

    decision, _ = decision_home_spread(row)
    close, _ = closing_home_spread(row)
    pick = str(row.get("Model Pick") or "Model pick")
    pick_decision = selected_team_spread(row, decision)
    pick_close = selected_team_spread(row, close)
    close_edge = closing_line_edge_text(row)
    explicit_source = str(row.get("_spread_source") or "")

    if np.isfinite(pick_decision):
        line_text = f"Saved spread: {pick} {pick_decision:+.1f}"
        if np.isfinite(pick_close):
            line_text += f" · closing line {pick_close:+.1f}"
            if close_edge:
                line_text += f" · {close_edge}"
    elif spread is not None and explicit_source:
        line_text = f"Spread result supplied by grader ({explicit_source})"
    elif np.isfinite(pick_close):
        line_text = f"Closing line {pick_close:+.1f} saved for reference · spread result needs a pregame/taken line"
    else:
        line_text = "Spread not graded — no pregame/taken sportsbook line was saved"

    headline = "ML + SPREAD SWEEP" if state == "sweep" else ("WINNING RESULT" if state == "win" else "FINAL RESULT")
    return compact_html(f"""
      <div class="result-banner {state}">
        <div class="result-mark">{mark}</div>
        <div class="result-copy"><div class="result-headline">{esc(headline)}</div><div class="result-final">{esc(score_text)}</div></div>
        <div class="result-outcomes">{pill('ML', ml, 'ml-win', 'Moneyline / straight-up winner: did the model pick the team that won the game?')}{pill('SPREAD', spread, 'spread-win', 'Spread result: did the model pick cover the saved pregame or taken sportsbook spread?')}</div>
        <div class="result-line">{esc(line_text)}</div>
      </div>
    """)

def _fmt(value: float, digits: int = 1, suffix: str = "") -> str:
    return fmt_num(value, digits, suffix) if np.isfinite(value) else "—"


def _profile_metric(label: str, value: object, note: str = "", tooltip: str = "") -> str:
    note_html = f'<span class="profile-note">{esc(note)}</span>' if note else ""
    help_html = f'<span class="help-dot" data-tooltip="{esc(tooltip)}" aria-label="{esc(tooltip)}" tabindex="0">?</span>' if tooltip else ""
    title_attr = f' title="{esc(tooltip)}"' if tooltip else ""
    return f'<div class="profile-metric"{title_attr}><span>{esc(label)}{help_html}</span><strong>{esc(value)}</strong>{note_html}</div>'


def metric_glossary_html() -> str:
    return compact_html("""
      <details class="metric-glossary">
        <summary>What do these numbers mean?</summary>
        <div class="metric-glossary-grid">
          <div><strong>Offense rating</strong><span>Points scored per 100 possessions after adjusting for opponent strength. Higher is better.</span></div>
          <div><strong>Defense rating</strong><span>Points allowed per 100 possessions after adjusting for opponent strength. Lower is better.</span></div>
          <div><strong>Overall rating</strong><span>Offense rating minus defense rating. Higher means a stronger overall efficiency profile.</span></div>
          <div><strong>Schedule strength</strong><span>How difficult the team's Division I schedule has been. Higher means tougher competition.</span></div>
          <div><strong>Typical margin swing</strong><span>How uncertain the projected winning margin is. A larger number means a more unpredictable game.</span></div>
          <div><strong>Data confidence</strong><span>How complete and reliable the inputs are for this matchup. Higher is better.</span></div>
          <div><strong>Model-implied odds</strong><span>American odds implied by the model's win probability. This is not a sportsbook quote.</span></div>
        </div>
      </details>
    """)

def _team_profile_card(row: pd.Series, team: str, focus_team: str) -> str:
    prefix = _team_prefix(row, team)
    is_pick = team == str(row.get("Model Pick") or "")
    is_focus = team == focus_team
    role = "MODEL PICK" if is_pick else ("FOCUS TEAM" if is_focus else "OPPONENT")
    ppg = _ppg(row, prefix)
    ppga = _ppga(row, prefix)
    metrics = "".join([
        _profile_metric("Offense rating", _fmt(_num(row, f"{prefix} AdjO")), "higher is better", "Opponent-adjusted points scored per 100 possessions. Higher is better."),
        _profile_metric("Defense rating", _fmt(_num(row, f"{prefix} AdjD")), "lower is better", "Opponent-adjusted points allowed per 100 possessions. Lower is better."),
        _profile_metric("Overall rating", _fmt(_num(row, f"{prefix} AdjNet")), "higher is better", "Offense rating minus defense rating. Higher means a stronger overall efficiency profile."),
        _profile_metric("Schedule strength", _fmt(_sos_value(row, team)), "higher = tougher", "How difficult this team's Division I schedule has been. Higher means tougher competition."),
        _profile_metric("Points / game", _fmt(ppg), "pregame average", "Average points scored per game before this matchup."),
        _profile_metric("Points allowed / game", _fmt(ppga), "pregame average", "Average points allowed per game before this matchup."),
        _profile_metric("Matchup edge", _fmt(_num(row, f"{prefix} Matchup Adj /100")), "positive helps team", "A small model adjustment for how the teams' styles and strengths interact. Positive favors the team shown."),
        _profile_metric("Player-status impact", _fmt(_num(row, f"{prefix} Availability Adj"), 1, " pts"), "availability effect", "Estimated point impact from known player availability. Treat cautiously when player status is not verified."),
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
    foot = "" if has_ppg else '<div class="dossier-footnote">Points-per-game averages will appear when true pregame values are published. Projected scores are never used as a substitute.</div>'
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

    if np.isfinite(net_gap):
        strength_text = f"{focus} +{net_gap:.1f}" if net_gap >= 0 else f"{other} +{abs(net_gap):.1f}"
    else:
        strength_text = "—"
    if np.isfinite(sos_gap):
        schedule_text = f"{focus} tougher by {sos_gap:.1f}" if sos_gap >= 0 else f"{other} tougher by {abs(sos_gap):.1f}"
    else:
        schedule_text = "—"

    return compact_html(f"""
      <div class="battle-shell">
        <div class="battle-title">HOW THE TEAMS MATCH UP</div>
        <div class="battle-grid">
          <div class="battle-card" title="Offense rating versus the opponent's defense rating. Offense: higher is better. Defense: lower is better."><span>{esc(focus)} offense vs defense</span><strong>{_fmt(focus_o)} vs {_fmt(other_d)}</strong><em>offense rating vs {esc(other)} defense rating</em></div>
          <div class="battle-card" title="Offense rating versus the opponent's defense rating. Offense: higher is better. Defense: lower is better."><span>{esc(other)} offense vs defense</span><strong>{_fmt(other_o)} vs {_fmt(focus_d)}</strong><em>offense rating vs {esc(focus)} defense rating</em></div>
          <div class="battle-card" title="Difference in overall opponent-adjusted team efficiency. Higher overall rating is better."><span>Overall team-strength edge</span><strong>{esc(strength_text)}</strong><em>bigger advantage = stronger overall profile</em></div>
          <div class="battle-card" title="Difference in schedule-strength rating. Higher schedule strength means tougher competition faced."><span>Tougher schedule</span><strong>{esc(schedule_text)}</strong><em>who has faced stronger competition</em></div>
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




def _pct_text(value: float) -> str:
    return f"{value:.0f}%" if np.isfinite(value) else "—"


def game_context_chips_html(row: pd.Series) -> str:
    flags = context_flags(row)
    chips: list[str] = []
    hr, ar = flags.get("home_rank"), flags.get("away_rank")
    if flags["ranked_vs_ranked"]:
        chips.append(f'<span class="chip spotlight">Ranked matchup #{ar} vs #{hr}</span>')
    if flags["conference_game"]:
        chips.append('<span class="chip conference">Conference game</span>')
    if flags["saturday"] and flags["prime_time"]:
        chips.append('<span class="chip primetime">Saturday night</span>')
    elif flags["prime_time"]:
        chips.append('<span class="chip primetime">Prime-time window</span>')
    if flags["spotlight"]:
        chips.append('<span class="chip spotlight strong">Market Spotlight</span>')
    return "".join(chips)


def market_interpretation_text(row: pd.Series) -> str:
    """Plain-English bettor read of ticket %, money %, and line movement.

    The wording intentionally avoids claiming that larger wagers are "sharp" or
    that a split creates an automatic betting edge. It says what the market is
    doing in language a casual bettor can understand.
    """
    f = market_features(row)
    ticket_team, money_team = f["ticket_team"], f["money_team"]
    ticket_pct, money_pct = f["ticket_pct"], f["money_pct"]
    model_pick = str(row.get("Model Pick") or "")
    sentences: list[str] = []

    if ticket_team and money_team:
        if ticket_team != money_team:
            sentences.append(
                f"Most bets are on {ticket_team} ({ticket_pct:.0f}%), but most of the money is on {money_team} ({money_pct:.0f}%). "
                f"Fewer bets are backing {money_team}, but those bets represent more dollars."
            )
        else:
            gap = money_pct - ticket_pct if np.isfinite(ticket_pct) and np.isfinite(money_pct) else float("nan")
            if np.isfinite(gap) and gap >= 10:
                sentences.append(
                    f"{ticket_team} has {ticket_pct:.0f}% of the bets and {money_pct:.0f}% of the money. "
                    f"The dollars are even more one-sided than the ticket count, which means the average bet on {ticket_team} is larger."
                )
            elif np.isfinite(gap) and gap <= -10:
                sentences.append(
                    f"{ticket_team} has {ticket_pct:.0f}% of the bets but only {money_pct:.0f}% of the money. "
                    f"A lot of people are betting {ticket_team}, but the dollars are less convinced."
                )
            elif np.isfinite(ticket_pct) and ticket_pct >= 65:
                sentences.append(
                    f"The crowd and the money both favor {ticket_team}: {ticket_pct:.0f}% of bets and {money_pct:.0f}% of the money are on that side."
                )
            else:
                sentences.append(
                    f"Bets and money are leaning the same way toward {ticket_team}, but the split is not extreme."
                )
    elif ticket_team:
        sentences.append(f"Most bets are on {ticket_team} ({ticket_pct:.0f}%). Money-split data is not available for this snapshot.")
    elif money_team:
        sentences.append(f"Most of the money is on {money_team} ({money_pct:.0f}%). Ticket-split data is not available for this snapshot.")

    if f["reverse_line_movement"] and f["line_move_team"]:
        sentences.append(
            f"The line is moving away from the popular side and toward {f['line_move_team']}. "
            "Bettors watch this because the sportsbook market is not following the crowd."
        )
    elif f["line_move_team"] and np.isfinite(f["line_move_points"]):
        move_team = f["line_move_team"]
        if ticket_team and money_team and ticket_team != money_team and move_team == money_team:
            sentences.append(
                f"The line has moved {f['line_move_points']:.1f} points toward {move_team}, the side with more money but fewer bets. "
                "That is a stronger market disagreement than the percentages alone."
            )
        elif ticket_team and money_team and move_team == ticket_team == money_team:
            sentences.append(
                f"The line has moved {f['line_move_points']:.1f} points toward {move_team} too, so the bets, the money, and the line are all moving the same way."
            )
        elif ticket_team and move_team == ticket_team:
            sentences.append(f"The line has moved {f['line_move_points']:.1f} points toward {move_team}, in the same direction as the public.")
        else:
            sentences.append(f"The line has moved {f['line_move_points']:.1f} points toward {move_team}.")

    if model_pick and ticket_team and money_team:
        if ticket_team != money_team and model_pick == money_team:
            sentences.append(f"The model is also on {model_pick}, so the model agrees with the money side rather than the more popular side.")
        elif model_pick == ticket_team == money_team:
            sentences.append(f"The model also likes {model_pick}. The model, the public, and the money all agree, but agreement is not a guarantee.")
        elif model_pick != ticket_team and model_pick != money_team:
            sentences.append(f"The model is on {model_pick}, while both the public and the money prefer the other side. This is a true model-versus-market disagreement.")

    return " ".join(sentences[:3])


def betting_crowd_read(row: pd.Series) -> str:
    """Public, non-numeric betting-split interpretation.

    Raw Owls Insight percentages remain owner-only. This function uses only
    qualitative public/sharp-money fields persisted in public game context.
    """
    note = str(row.get("Betting Note") or "").strip()
    if not note:
        return ""
    public_side = str(row.get("Betting Public Side") or "").strip()
    money_side = str(row.get("Betting Money Side") or "").strip()
    f = market_features(row)
    move_team = str(f.get("line_move_team") or "").strip()
    move_pts = f.get("line_move_points")
    extras: list[str] = []
    if move_team and np.isfinite(move_pts) and float(move_pts) >= 0.5:
        if money_side and move_team == money_side and public_side and money_side != public_side:
            extras.append(f"The line is moving toward {move_team}, the same side favored by the money rather than the larger number of bets.")
        elif public_side and move_team != public_side:
            extras.append(f"The sportsbook line is moving toward {move_team}, against the more popular betting side. That disagreement is worth watching.")
        elif public_side and move_team == public_side:
            extras.append(f"The line is also moving toward {move_team}, so the market price is following the betting crowd.")
    return " ".join([note, *extras]).strip()


def betting_market_note_html(row: pd.Series) -> str:
    read = betting_crowd_read(row)
    if not read:
        return ""
    label = str(row.get("Betting Label") or "Betting crowd check")
    html = (
        f'<div class="intel-callout market-note">'
        f'<strong>{esc(label)}</strong>'
        f'<span>{esc(read)}</span>'
        f'<small>Betting-market context only. These splits do not change the production model prediction.</small>'
        f'</div>'
    )
    return compact_html(html)


def market_pulse_html(row: pd.Series) -> str:
    f = market_features(row)
    line_provider = str(row.get("_market_source_label") or "")
    line_latest = str(row.get("_market_latest_snapshot_utc") or "")
    betting_label = str(row.get("Betting Label") or "").strip()
    betting_read = betting_crowd_read(row)
    opening = _num(row, "_market_opening_home_spread")
    current = _num(row, "_market_current_home_spread")
    home = str(row.get("Home Team") or "Home")
    if not betting_read and not (np.isfinite(opening) or np.isfinite(current)):
        return compact_html('<div class="market-pulse empty"><div class="market-pulse-head"><span>MARKET PULSE</span></div><div class="market-empty">Sportsbook lines and betting-crowd context are not available for this game yet.</div></div>')

    if np.isfinite(current):
        line_value = f"{home} {current:+.1f}"
    elif np.isfinite(opening):
        line_value = f"{home} {opening:+.1f}"
    else:
        line_value = "--"

    if np.isfinite(opening) and np.isfinite(current) and abs(opening - current) >= 0.05:
        move_value = f"{opening:+.1f} to {current:+.1f}"
        if f["line_move_team"] and np.isfinite(f["line_move_points"]):
            move_note = f"{f['line_move_points']:.1f} pts toward {f['line_move_team']}"
        else:
            move_note = "tracked movement"
    elif np.isfinite(current):
        move_value = "First snapshot"
        move_note = "movement starts here"
    else:
        move_value = "--"
        move_note = "no movement data"

    book_agreement = str(row.get("_market_book_agreement") or "").lower()
    book_range = _num(row, "_market_book_spread_range")
    book_count = _num(row, "_market_book_count")
    agreement_labels = {"tight": "Tight", "mixed": "Mixed", "wide": "Wide"}
    agreement_value = agreement_labels.get(book_agreement, "Available" if np.isfinite(book_range) else "--")
    agreement_note_parts: list[str] = []
    if np.isfinite(book_count):
        agreement_note_parts.append(f"{int(book_count)} books")
    if np.isfinite(book_range):
        agreement_note_parts.append(f"{book_range:.1f} pt range")
    agreement_note = " · ".join(agreement_note_parts) if agreement_note_parts else "cross-book spread view"

    source_text = "Published market data"
    if line_provider:
        stamp = f"{line_latest[11:16]} UTC" if len(line_latest) >= 16 else ""
        source_text = f"Lines: {line_provider}" + (f" · {stamp}" if stamp else "")
    if betting_read:
        source_text += " | Betting flow: owner-authorized crowd/sharp read"

    read_text = betting_read
    if book_agreement == "wide" and np.isfinite(book_range):
        extra = f"Sportsbooks disagree by as much as {book_range:.1f} points on the spread."
        read_text = f"{read_text} {extra}".strip()
    read_html = f'<div class="market-pulse-read"><strong>WHAT IT MEANS</strong><span>{esc(read_text)}</span></div>' if read_text else ""
    css = "reverse" if f["reverse_line_movement"] else "live"

    if betting_read:
        crowd_value = betting_label or "Betting split available"
        stats = (
            f'<div class="market-pulse-stat"><span>SPORTSBOOK LINE</span><strong>{esc(line_value)}</strong><small>current reference line</small></div>'
            f'<div class="market-pulse-stat"><span>BETTING CROWD</span><strong>{esc(crowd_value)}</strong><small>plain-English split read</small></div>'
            f'<div class="market-pulse-stat"><span>LINE MOVEMENT</span><strong>{esc(move_value)}</strong><small>{esc(move_note)}</small></div>'
        )
    else:
        stats = (
            f'<div class="market-pulse-stat"><span>SPORTSBOOK LINE</span><strong>{esc(line_value)}</strong><small>current reference line</small></div>'
            f'<div class="market-pulse-stat"><span>LINE MOVEMENT</span><strong>{esc(move_value)}</strong><small>{esc(move_note)}</small></div>'
            f'<div class="market-pulse-stat"><span>BOOK CONSENSUS</span><strong>{esc(agreement_value)}</strong><small>{esc(agreement_note)}</small></div>'
        )

    html = (
        f'<div class="market-pulse {css}">'
        f'<div class="market-pulse-head"><span>MARKET PULSE</span><em>{esc(source_text)}</em></div>'
        f'<div class="market-pulse-grid">{stats}</div>'
        f'{read_html}</div>'
    )
    return compact_html(html)


def market_context_html(row: pd.Series) -> str:
    decision, decision_source = decision_home_spread(row)
    close, _ = closing_home_spread(row)
    pick = str(row.get("Model Pick") or "Model pick")
    selected_decision = selected_team_spread(row, decision)
    selected_close = selected_team_spread(row, close)
    gap = model_market_gap(row)
    close_edge = closing_line_edge_text(row)

    if not np.isfinite(selected_decision):
        close_note = f' A closing line of {selected_close:+.1f} is saved for reference only.' if np.isfinite(selected_close) else ""
        return compact_html(f"""
          <div class="market-context neutral">
            <div><span>SPORTSBOOK COMPARISON</span><strong>No pregame sportsbook spread saved</strong></div>
            <p>The prediction was made without using sportsbook lines.{esc(close_note)} The site will not grade the spread without a saved pregame/taken line.</p>
          </div>
        """)

    if np.isfinite(gap):
        if gap > 0:
            gap_text = f"Sportsbook gives the pick {gap:.1f} more points than the model spread"
        elif gap < 0:
            gap_text = f"Sportsbook line is {abs(gap):.1f} points less favorable than the model spread"
        else:
            gap_text = "Sportsbook and model spread match"
    else:
        gap_text = "Model-versus-sportsbook difference unavailable"
    close_html = ""
    if np.isfinite(selected_close):
        edge = f" · {close_edge}" if close_edge else ""
        close_html = f'<span class="market-close">Closing line {selected_close:+.1f}{esc(edge)}</span>'
    return compact_html(f"""
      <div class="market-context live">
        <div><span>SPORTSBOOK COMPARISON</span><strong>{esc(pick)} {selected_decision:+.1f}</strong></div>
        <div class="market-gap">{esc(gap_text)}</div>{close_html}
        <p>This comparison is display-only. Sportsbook lines do not change the production prediction and this is not an automatic bet recommendation. Source: {esc(decision_source or 'published line')}.</p>
      </div>
    """)

def _archive_book(row: pd.Series, field: str) -> str:
    value = row.get(field)
    if value is None:
        return ""
    text = str(value).strip()
    return "" if not text or text.lower() in {"nan", "none"} else text

def _spread_quote(line: float, price: float, book: str) -> str:
    if not np.isfinite(line):
        return "—"
    price_text = f" ({fmt_odds(price)})" if np.isfinite(price) else ""
    book_text = f" · {esc(book)}" if book else ""
    return f"{line:+.1f}{price_text}{book_text}"

def best_odds_html(row: pd.Series) -> str:
    """Best available Owls quotes from our independent scheduled historical archive."""
    pick = str(row.get("Model Pick") or "")
    home = str(row.get("Home Team") or "")
    side = "home" if pick == home else "away"

    current_spread = _num(row, f"_best_current_spread_{side}_line")
    current_spread_price = _num(row, f"_best_current_spread_{side}_price")
    current_spread_book = _archive_book(row, f"_best_current_spread_{side}_book_title")
    current_ml = _num(row, f"_best_current_moneyline_{side}_price")
    current_ml_book = _archive_book(row, f"_best_current_moneyline_{side}_book_title")
    open_spread = _num(row, f"_best_open_spread_{side}_line")
    open_book = _archive_book(row, f"_best_open_spread_{side}_book_title")
    close_spread = _num(row, f"_best_close_spread_{side}_line")
    close_book = _archive_book(row, f"_best_close_spread_{side}_book_title")
    updated = row.get("_best_current_spread_captured_at_utc") or row.get("_best_current_moneyline_captured_at_utc")

    if not any(np.isfinite(x) for x in [current_spread, current_ml, open_spread, close_spread]):
        return ""

    spread_text = _spread_quote(current_spread, current_spread_price, current_spread_book)
    ml_text = f"{fmt_odds(current_ml)} · {esc(current_ml_book)}" if np.isfinite(current_ml) else "—"
    if np.isfinite(open_spread):
        open_text = f"{open_spread:+.1f}" + (f" · {esc(open_book)}" if open_book else "")
    else:
        open_text = "—"
    move = current_spread - open_spread if np.isfinite(current_spread) and np.isfinite(open_spread) else float("nan")
    if np.isfinite(move):
        if abs(move) < 0.05:
            move_text = "0.0 pts"
        elif move > 0:
            move_text = f"+{move:.1f} pts better"
        else:
            move_text = f"{move:.1f} pts worse"
    else:
        move_text = "—"
    close_text = f"{close_spread:+.1f}" + (f" · {esc(close_book)}" if close_book else "") if np.isfinite(close_spread) else "Pending"

    decision, _ = decision_home_spread(row)
    selected_decision = selected_team_spread(row, decision)
    clv_text = "Pending"
    if np.isfinite(selected_decision) and np.isfinite(close_spread):
        clv = selected_decision - close_spread
        if abs(clv) < 0.05:
            clv_text = "0.0 pts"
        elif clv > 0:
            clv_text = f"+{clv:.1f} pts"
        else:
            clv_text = f"{clv:.1f} pts"

    updated_text = ""
    stamp = pd.to_datetime(updated, utc=True, errors="coerce")
    if pd.notna(stamp):
        updated_text = f" · archived {stamp.strftime('%b %d %H:%M UTC')}"

    return compact_html(f"""
      <div class="market-pulse">
        <div class="market-pulse-head"><span>BEST SPORTSBOOK ODDS</span><strong>{esc(pick)}{esc(updated_text)}</strong></div>
        <div class="market-pulse-grid">
          <div class="market-pulse-stat"><span>Best spread now</span><strong>{spread_text}</strong><em>best point first, then best price</em></div>
          <div class="market-pulse-stat"><span>Best moneyline now</span><strong>{ml_text}</strong><em>highest available American price</em></div>
          <div class="market-pulse-stat"><span>Tracked open</span><strong>{open_text}</strong><em>first quote our archive observed</em></div>
          <div class="market-pulse-stat"><span>Best-line move</span><strong>{esc(move_text)}</strong><em>current best spread vs tracked open</em></div>
          <div class="market-pulse-stat"><span>Tracked close</span><strong>{close_text}</strong><em>last captured pregame market</em></div>
          <div class="market-pulse-stat"><span>Best-market CLV</span><strong>{esc(clv_text)}</strong><em>saved decision line vs tracked best close</em></div>
        </div>
      </div>
    """)
def betting_snapshot_html(row: pd.Series) -> str:
    metrics = "".join([
        _profile_metric("Model spread", fmt_spread(row.get("Fair Spread")), "projected point spread", "The point spread implied by the model's projected score. Negative means the picked team is favored."),
        _profile_metric("Model-implied odds", fmt_odds(row.get("Fair Moneyline")), "not a sportsbook quote", "American odds implied by the model's win probability. This is not a sportsbook price."),
        _profile_metric("Projected combined points", fmt_num(row.get("Projected Total"), 1), "both teams combined", "The model's expected total points scored by both teams."),
        _profile_metric("Projected game speed", fmt_num(row.get("Expected Pace"), 1), "estimated possessions", "Estimated number of possessions in the game. More possessions usually means a faster game."),
        _profile_metric("Data confidence", f"{fmt_num(row.get('Data Quality'),0)}/100", "higher is better", "How complete and reliable the model inputs are for this matchup. Higher is better."),
    ])
    return compact_html(f'<div class="betting-snapshot">{metrics}</div>')

def dossier_html(row: pd.Series) -> str:
    availability = "Verified" if _bool(row.get("Availability Verified", False)) else "Not verified"
    site = "Neutral court" if _bool(row.get("Neutral Site", False)) else "Campus / scheduled site"
    context = compact_html(f"""
      <div class="dossier-context-grid">
        <div class="dossier-context" title="A plain-language summary of how strongly the model favors the selected team."><span>Pick strength</span><strong>{esc(projection_tier(row))}</strong></div>
        <div class="dossier-context" title="How uncertain the projected winning margin is. Bigger numbers mean a more unpredictable game."><span>Typical margin swing</span><strong>{esc(margin_swing_text(row))}</strong></div>
        <div class="dossier-context" title="Whether the model has verified player availability information for this matchup."><span>Player status</span><strong>{esc(availability)}</strong></div>
        <div class="dossier-context"><span>Location</span><strong>{esc(site)}</strong></div>
        <div class="dossier-context" title="How complete and reliable the model inputs are. Higher is better."><span>Data confidence</span><strong>{fmt_num(row.get('Data Quality'),0)}/100</strong></div>
      </div>
    """)
    return compact_html(f"""
      <details class="intel-dossier">
        <summary><span>Why this pick?</span><span>Reasons / risks / team comparison / sportsbook context ＋</span></summary>
        <div class="dossier-body">{evidence_html(row)}{betting_market_note_html(row)}{team_snapshot_html(row)}{matchup_battle_html(row)}{market_pulse_html(row)}{market_context_html(row)}{context}{metric_glossary_html()}</div>
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
        f'<span class="chip {"teal" if d1 else "gold"}">{"Both teams Division I" if d1 else "Other matchup"}</span>',
        f'<span class="chip projection">{esc(projection_tier(row))}</span>',
    ]
    if neutral:
        chips.append('<span class="chip orange">Neutral court</span>')
    chips.append(f'<span class="chip {"green" if verified else "gold"}">{"Player status verified" if verified else "Player status not verified"}</span>')
    chips.append(f'<span class="chip champion">{esc(model_role(row))}</span>')
    context_chips = game_context_chips_html(row)
    if context_chips:
        chips.append(context_chips)
    decision, _ = decision_home_spread(row)
    selected_decision = selected_team_spread(row, decision)
    gap = model_market_gap(row)
    if np.isfinite(selected_decision):
        gap_text = f" · differs {abs(gap):.1f} pts" if np.isfinite(gap) and abs(gap) >= .05 else ""
        chips.append(f'<span class="chip market">Sportsbook {selected_decision:+.1f}{esc(gap_text)}</span>')

    def team_row(name: str, score: Any) -> str:
        tag = '<span class="team-tag">MODEL PICK</span>' if name == pick else ""
        return f'<div class="team-row {"pick" if name == pick else ""}"><div class="team-name">{esc(name)}{tag}</div><div class="score">{fmt_num(score,1)}</div></div>'

    result = _result_banner(row)

    return compact_html(f"""
      <div class="game-card {cls}">
        {result}
        <div class="game-head">
          <div><span class="rank-pill">#{rank}</span><div class="game-time">{esc(start_text)} · {"Neutral court" if neutral else "Campus / scheduled site"}</div></div>
          <div><div class="prob">{fmt_pct(prob)}</div><div class="prob-label">Chance model pick wins</div><div class="model-pick">{esc(pick)} {fmt_spread(row.get('Fair Spread'))}</div></div>
        </div>
        <div class="scoreboard">{team_row(away, row.get('Projected Away Score'))}{team_row(home, row.get('Projected Home Score'))}</div>
        <div class="chip-row">{''.join(chips)}</div>
        {best_odds_html(row)}
        {market_pulse_html(row)}
        {betting_snapshot_html(row)}
        {dossier_html(row)}
      </div>
    """)

def game_card_grid_html(frame: pd.DataFrame) -> str:
    cards = "".join(game_card_html(row) for _, row in frame.iterrows())
    return compact_html(f'<div class="game-card-grid">{cards}</div>')
