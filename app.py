from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from cbb_dashboard.charts import (
    calibration_chart,
    confidence_chart,
    performance_trend,
    team_comparison_chart,
)
from cbb_dashboard.data import (
    DataValidationError,
    attach_grading,
    board_table,
    normalize_board,
    normalize_graded_board,
    read_csv,
)
from cbb_dashboard.intelligence import (
    compact_html,
    evidence_html,
    game_card_grid_html,
    game_card_html,
    market_context_html,
    matchup_battle_html,
    team_profile_pair_html,
)
from cbb_dashboard.performance import (
    aggregate_metrics,
    confidence_buckets,
    history_frame,
    top_k_summary,
)
from cbb_dashboard.security import audit_actor, evaluate_admin_identity
from cbb_dashboard.storage import (
    StoreConfig,
    StorageConfigurationError,
    StorageOperationError,
    SupabaseSlateStore,
)
from cbb_dashboard.ui import GLOBAL_CSS, esc, fmt_num, fmt_pct, fmt_spread

PROJECT_ROOT = Path(__file__).resolve().parent
BRAND = "CBB MODEL"
APP_VERSION = "1.3.4"

st.set_page_config(
    page_title="CBB Model | Betting Intelligence",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def secret(name: str, default: Any = None) -> Any:
    try:
        return st.secrets[name]
    except Exception:
        return default


def auth_is_configured() -> bool:
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def current_user_dict() -> dict[str, Any]:
    try:
        user = st.user
        if hasattr(user, "to_dict"):
            return dict(user.to_dict())
        return dict(user)
    except Exception:
        return {}


def make_store() -> tuple[SupabaseSlateStore | None, str | None]:
    url = str(secret("SUPABASE_URL", "") or "").strip()
    publishable = str(
        secret("SUPABASE_PUBLISHABLE_KEY", "")
        or secret("SUPABASE_ANON_KEY", "")
        or ""
    ).strip()
    server_key = str(
        secret("SUPABASE_SECRET_KEY", "")
        or secret("SUPABASE_SERVICE_ROLE_KEY", "")
        or ""
    ).strip() or None
    if not url or not publishable:
        return None, "Persistent storage is not configured."
    try:
        return SupabaseSlateStore(StoreConfig(url, publishable, server_key)), None
    except Exception as exc:
        return None, f"Persistent storage could not initialize: {type(exc).__name__}"


def metric_card(label: str, value: str, foot: str = "", tooltip: str = "") -> None:
    help_html = f'<span class="help-dot" data-tooltip="{esc(tooltip)}" aria-label="{esc(tooltip)}" tabindex="0">?</span>' if tooltip else ""
    title_attr = f' title="{esc(tooltip)}"' if tooltip else ""
    st.markdown(
        compact_html(f"""
        <div class="metric-shell"{title_attr}>
          <div class="metric-label">{esc(label)}{help_html}</div>
          <div class="metric-value">{esc(value)}</div>
          <div class="metric-foot">{esc(foot)}</div>
        </div>
        """),
        unsafe_allow_html=True,
    )

def _numeric_board_series(board: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    """Return a numeric Series even when an optional column is absent.

    Historical published slates do not contain Champion-only fields.  Returning
    a Series instead of the scalar produced by ``DataFrame.get`` keeps the UI
    backward-compatible with those archived boards.
    """
    if column in board.columns:
        return pd.to_numeric(board[column], errors="coerce")
    return pd.Series(default, index=board.index, dtype=float)


def status_strip(report, board: pd.DataFrame) -> None:
    d1_pct = (report.d1_games / report.rows) if report.rows else 0.0
    verified = float(board["_availability_verified"].mean()) if len(board) and "_availability_verified" in board.columns else 0.0
    quality = _numeric_board_series(board, "Data Quality").mean()
    graded_mask = board.get("_grade_eligible", pd.Series(False, index=board.index)).fillna(False).astype(bool)
    finals = int(graded_mask.sum())
    spread_known = int(board.loc[graded_mask, "_spread_correct"].notna().sum()) if finals and "_spread_correct" in board.columns else 0
    is_champion = str(report.model_version).upper() == "1.1.3B"
    engine_value = "Production model" if is_champion else "Historical model"
    slate_value = f"Final {finals}/{len(board)}" if finals else "Pregame"
    slate_detail = f"{spread_known} game(s) have a saved spread" if finals else "Published before games started"
    html = f"""
    <div class="status-strip">
      <div class="status-item"><div class="status-top"><span class="status-dot fresh"></span>Model</div><div class="status-value">{esc(engine_value)}</div><div class="status-detail">Version {esc(report.model_version)}</div></div>
      <div class="status-item" title="Games where both teams are Division I."><div class="status-top"><span class="status-dot info"></span>Division I games</div><div class="status-value">{report.d1_games}/{report.rows} games</div><div class="status-detail">{d1_pct:.0%} of this slate</div></div>
      <div class="status-item" title="How much of the slate has verified pregame player availability information."><div class="status-top"><span class="status-dot {'fresh' if verified >= .99 else 'warn'}"></span>Player status</div><div class="status-value">{verified:.0%} verified</div><div class="status-detail">Pregame availability coverage</div></div>
      <div class="status-item" title="A 0-100 score for how complete and reliable the model inputs are. Higher is better."><div class="status-top"><span class="status-dot {'fresh' if pd.notna(quality) and quality >= 65 else 'warn'}"></span>Data confidence</div><div class="status-value">{fmt_num(quality,0)}/100</div><div class="status-detail">Average input quality</div></div>
      <div class="status-item"><div class="status-top"><span class="status-dot {'fresh' if finals else 'info'}"></span>Game results</div><div class="status-value">{esc(slate_value)}</div><div class="status-detail">{esc(slate_detail)}</div></div>
    </div>
    """
    st.markdown(compact_html(html), unsafe_allow_html=True)

def published_time(record: dict[str, Any] | None) -> str:
    raw = (record or {}).get("published_at")
    if not raw:
        return ""
    try:
        return pd.to_datetime(raw, utc=True).strftime("%b %d, %Y %H:%M UTC")
    except Exception:
        return str(raw)


def render_header(report, record: dict[str, Any] | None) -> None:
    rev = (record or {}).get("revision") or 1
    stamp = published_time(record)
    publication = f"Published revision {rev}" + (f" • {stamp}" if stamp else "")
    role = "Production Champion" if str(report.model_version).upper() == "1.1.3B" else "Historical"
    st.markdown('<div class="cbb-kicker">COLLEGE BASKETBALL INTELLIGENCE</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="cbb-title">{BRAND} <span style="color:#fbbf24">//</span> CHAMPION TERMINAL</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="cbb-subtitle">{esc(report.slate_date)} &nbsp;•&nbsp; {esc(role)} V{esc(report.model_version)} &nbsp;•&nbsp; {esc(publication)}</div>',
        unsafe_allow_html=True,
    )

def render_empty_state(store_error: str | None) -> None:
    st.markdown('<div class="cbb-kicker">COLLEGE BASKETBALL INTELLIGENCE</div>', unsafe_allow_html=True)
    st.markdown('<div class="cbb-title">CBB MODEL <span style="color:#fbbf24">//</span> CHAMPION TERMINAL</div>', unsafe_allow_html=True)
    st.markdown('<div class="cbb-subtitle">Public read-only analytics interface • No slate is currently published.</div>', unsafe_allow_html=True)
    if store_error:
        st.info("Publishing storage has not been configured for this deployment yet. Public upload controls remain disabled.")
    else:
        st.info("No compatible CBB decision board is available yet. Sign in as the authorized owner to publish the first slate.")
    st.markdown(
        '<div class="firewall-note"><strong>Model firewall:</strong> the website reads published model output. It does not rerun, rescore, or modify the independent CBB prediction engine.</div>',
        unsafe_allow_html=True,
    )

def format_board_for_table(board: pd.DataFrame) -> pd.DataFrame:
    out = board_table(board)
    # Remove simulation internals from the public table; the card translates them into a plain-English outcome range.
    out = out.drop(columns=[c for c in ["Home Margin P10", "Home Margin P90"] if c in out.columns], errors="ignore")
    if "Win Probability" in out.columns:
        out["Win Probability"] = pd.to_numeric(out["Win Probability"], errors="coerce").map(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
    spread_columns = [
        "Fair Spread", "Bet Home Spread", "Taken Home Spread", "Decision Home Spread",
        "Market Home Spread", "Sportsbook Home Spread", "Closing Home Spread",
    ]
    for c in spread_columns:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").map(lambda x: f"{x:+.1f}" if pd.notna(x) else "—")

    # Prefer the Division I schedule-strength fields when both old and new aliases exist.
    if "V1.1 Home D1 SOS" in out.columns:
        out = out.drop(columns=["Home SOS"], errors="ignore")
    if "V1.1 Away D1 SOS" in out.columns:
        out = out.drop(columns=["Away SOS"], errors="ignore")

    rename = {
        "D1 Rank": "Division I Rank",
        "Game Classification": "Game Type",
        "Fair Spread": "Model Spread",
        "Fair Moneyline": "Model-Implied Odds",
        "Projected Total": "Projected Combined Points",
        "Expected Pace": "Projected Game Speed",
        "Margin SD": "Typical Margin Swing",
        "Home AdjO": "Home Offense Rating",
        "Home AdjD": "Home Defense Rating",
        "Home AdjNet": "Home Overall Rating",
        "Away AdjO": "Away Offense Rating",
        "Away AdjD": "Away Defense Rating",
        "Away AdjNet": "Away Overall Rating",
        "V1.1 Home D1 SOS": "Home Schedule Strength",
        "V1.1 Away D1 SOS": "Away Schedule Strength",
        "Home SOS": "Home Schedule Strength",
        "Away SOS": "Away Schedule Strength",
        "Home PPG": "Home Points / Game",
        "Away PPG": "Away Points / Game",
        "Home PPG Allowed": "Home Points Allowed / Game",
        "Away PPG Allowed": "Away Points Allowed / Game",
        "Home Matchup Adj /100": "Home Matchup Edge",
        "Away Matchup Adj /100": "Away Matchup Edge",
        "Data Quality": "Data Confidence",
        "Availability Verified": "Player Status Verified",
        "Bet Home Spread": "Saved Home Spread",
        "Taken Home Spread": "Saved Home Spread",
        "Decision Home Spread": "Saved Home Spread",
        "Market Home Spread": "Saved Home Spread",
        "Sportsbook Home Spread": "Saved Home Spread",
        "Closing Home Spread": "Closing Home Spread",
    }
    out = out.rename(columns=rename)
    # Duplicate aliases can occur when multiple market spread fields are published. Keep the first visible copy.
    out = out.loc[:, ~out.columns.duplicated()].copy()
    return out

def apply_board_filters(board: pd.DataFrame) -> pd.DataFrame:
    st.markdown('<div class="section-title">Board filters</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    teams = sorted(set(board["Home Team"].astype(str)).union(set(board["Away Team"].astype(str))))
    with c1:
        selected_teams = st.multiselect("Teams", teams, placeholder="All teams")
    with c2:
        cohort = st.selectbox("Game type", ["All games", "Division I vs Division I", "Other games"])
    with c3:
        confidence_floor = st.slider("Minimum model win chance", 50, 95, 50, 1, help="Only show picks where the model gives its selected team at least this chance to win.")
    with c4:
        verified_only = st.toggle("Verified player status only", value=False, help="Show only games where player availability was explicitly verified before tip-off.")
    filtered = board.copy()
    if selected_teams:
        filtered = filtered[filtered["Home Team"].isin(selected_teams) | filtered["Away Team"].isin(selected_teams)]
    if cohort == "Division I vs Division I":
        filtered = filtered[filtered["_is_d1"]]
    elif cohort == "Other games":
        filtered = filtered[~filtered["_is_d1"]]
    filtered = filtered[filtered["_win_prob"] >= confidence_floor / 100.0]
    if verified_only:
        filtered = filtered[filtered["_availability_verified"]]
    return filtered

def render_board(board: pd.DataFrame, report) -> None:
    status_strip(report, board)
    d1 = board[board["_is_d1"]].copy()
    strongest = board.sort_values("_win_prob", ascending=False).iloc[0] if len(board) else None
    graded = board[board.get("_grade_eligible", pd.Series(False, index=board.index)).fillna(False).astype(bool)].copy()
    ml_wins = int(graded.get("_ml_correct", pd.Series(dtype="boolean")).fillna(False).sum()) if len(graded) else 0
    spread_known = graded.get("_spread_correct", pd.Series(dtype="boolean")).notna().sum() if len(graded) else 0
    spread_wins = int(graded.get("_spread_correct", pd.Series(dtype="boolean")).fillna(False).sum()) if len(graded) else 0
    clear_sides = int((pd.to_numeric(board["Win Probability"], errors="coerce") >= 0.60).sum())

    cols = st.columns(6)
    with cols[0]: metric_card("Games", f"{len(board)}", f"{report.d1_games} Division I matchups", "Division I matchup means both teams are Division I.")
    with cols[1]: metric_card("Strongest pick", str(strongest.get("Model Pick")) if strongest is not None else "—", fmt_pct(strongest.get("Win Probability")) if strongest is not None else "", "The team with the highest model win chance on this slate.")
    with cols[2]: metric_card("Strong model leans", f"{clear_sides}", "60%+ model win chance", "Number of picks where the model gives its selected team at least a 60% chance to win.")
    with cols[3]: metric_card("Neutral court", f"{int(board['_neutral'].sum())}", "No home-court location advantage")
    with cols[4]: metric_card("Winner picks", f"{ml_wins}-{len(graded)-ml_wins}" if len(graded) else "Pregame", "Straight-up game winners", "Moneyline / straight-up grading: did the model pick the team that won?")
    with cols[5]: metric_card("Spread picks", f"{spread_wins}-{int(spread_known)-spread_wins}" if spread_known else "—", "Only when a pregame line is saved", "Spread grading uses the saved pregame or taken sportsbook line. The closing line is tracked separately.")

    if len(graded):
        spread_note = f'<span class="grade-summary-pill gold">SPREAD {spread_wins}-{int(spread_known)-spread_wins}</span>' if spread_known else '<span class="grade-summary-pill muted">SPREAD — no pregame line saved</span>'
        st.markdown(f'<div class="grade-summary-strip"><span class="grade-summary-pill green">ML {ml_wins}-{len(graded)-ml_wins}</span>{spread_note}<span class="grade-summary-pill muted">{len(graded)} final games</span></div>', unsafe_allow_html=True)

    for warning in report.warnings:
        st.warning(warning, icon="⚠️")

    st.markdown('<div class="section-title">Priority board</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-note">Cards show the model pick, projected score and win chance first. Open <strong>Why this pick?</strong> for plain-English reasons, risks and team comparisons.</div>', unsafe_allow_html=True)
    scope = st.segmented_control("Card depth", ["Top 10", "All"], default="Top 10", label_visibility="collapsed")
    n = {"Top 10": 10, "All": len(board)}.get(scope, 10)
    st.markdown(game_card_grid_html(board.head(n)), unsafe_allow_html=True)

    filtered = apply_board_filters(board)
    st.markdown(f'<div class="section-title">Full decision board ({len(filtered)})</div>', unsafe_allow_html=True)
    st.caption("Hover over unfamiliar card metrics for definitions. The full table uses plain-English column names; technical model field names are hidden.")
    st.dataframe(format_board_for_table(filtered), use_container_width=True, hide_index=True, height=min(700, 70 + 35 * max(4, len(filtered))))

    if len(d1) >= 2:
        st.markdown('<div class="section-title">Strongest model picks</div>', unsafe_allow_html=True)
        st.plotly_chart(confidence_chart(d1, top_n=min(25, len(d1))), use_container_width=True)

def matchup_label(row: pd.Series) -> str:
    marker = " · N" if bool(row.get("Neutral Site", False)) else ""
    return f"#{int(row.get('_rank', 0))} {row.get('Away Team')} vs {row.get('Home Team')}{marker}"


def render_matchup_explorer(board: pd.DataFrame) -> None:
    st.markdown('<div class="cbb-kicker">GAME BREAKDOWN</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Matchup Explorer</div>', unsafe_allow_html=True)
    labels = {matchup_label(row): idx for idx, row in board.iterrows()}
    choice = st.selectbox("Select a matchup", list(labels.keys()))
    row = board.loc[labels[choice]]
    st.markdown(game_card_html(row), unsafe_allow_html=True)

    st.markdown('<div class="section-title">Team profiles</div>', unsafe_allow_html=True)
    st.markdown(team_profile_pair_html(row), unsafe_allow_html=True)
    st.markdown(matchup_battle_html(row), unsafe_allow_html=True)

    st.markdown('<div class="section-title">Team strength comparison</div>', unsafe_allow_html=True)
    st.plotly_chart(team_comparison_chart(row), use_container_width=True)

    st.markdown('<div class="section-title">Game projection</div>', unsafe_allow_html=True)
    from cbb_dashboard.intelligence import margin_swing_text
    pick = str(row.get("Model Pick") or "Model pick")
    home = str(row.get("Home Team") or "")
    projected_home_margin = pd.to_numeric(row.get("Projected Home Score"), errors="coerce") - pd.to_numeric(row.get("Projected Away Score"), errors="coerce")
    projected_pick_margin = projected_home_margin if pick == home else -projected_home_margin
    sim = st.columns(4)
    with sim[0]: metric_card("Projected winning margin", fmt_num(projected_pick_margin, 1, " pts"), f"{pick} perspective", "The model's projected score difference for the selected team.")
    with sim[1]: metric_card("Typical margin swing", margin_swing_text(row), "Bigger = more unpredictable", "How uncertain the projected winning margin is. Larger numbers mean the final margin can move farther from the projection.")
    with sim[2]: metric_card("Projected combined points", fmt_num(row.get("Projected Total"), 1), "Both teams combined", "The model's expected total points scored by both teams.")
    with sim[3]: metric_card("Projected game speed", fmt_num(row.get("Expected Pace"), 1), "Estimated possessions", "Estimated number of possessions. More possessions usually means a faster game.")

    st.markdown(market_context_html(row), unsafe_allow_html=True)

def team_rows(board: pd.DataFrame, team: str) -> pd.DataFrame:
    return board[(board["Home Team"].astype(str) == team) | (board["Away Team"].astype(str) == team)].copy()


def render_team_intelligence(board: pd.DataFrame) -> None:
    st.markdown('<div class="cbb-kicker">TEAM DOSSIER</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Team Intelligence</div>', unsafe_allow_html=True)
    teams = sorted(set(board["Home Team"].astype(str)).union(set(board["Away Team"].astype(str))))
    team = st.selectbox("Select team", teams)
    rows = team_rows(board, team)
    row = rows.sort_values("_rank").iloc[0]
    home = str(row.get("Home Team")) == team
    prefix = "Home" if home else "Away"
    opponent = str(row.get("Away Team" if home else "Home Team"))
    model_pick = str(row.get("Model Pick") or "")
    pick_note = "MODEL PICK" if model_pick == team else f"MODEL PREFERS {model_pick}"
    model_prob = pd.to_numeric(row.get("Win Probability"), errors="coerce")
    team_prob = model_prob if model_pick == team else (1 - model_prob if pd.notna(model_prob) else np.nan)
    st.markdown(f'<div class="team-dossier-hero"><div><span>{esc(pick_note)}</span><strong>{esc(team)}</strong><p>vs {esc(opponent)} · {"neutral court" if bool(row.get("Neutral Site",False)) else "scheduled site"}</p></div><div><span>CHANCE TO WIN</span><strong>{fmt_pct(team_prob)}</strong><p>According to the current model</p></div></div>', unsafe_allow_html=True)

    cols = st.columns(6)
    ppg = row.get(f"{prefix} PPG", row.get(f"{prefix} Points Per Game"))
    ppga = row.get(f"{prefix} PPG Allowed", row.get(f"{prefix} Points Allowed Per Game"))
    metrics = [
        ("Offense rating", row.get(f"{prefix} AdjO"), "higher is better", "Opponent-adjusted points scored per 100 possessions."),
        ("Defense rating", row.get(f"{prefix} AdjD"), "lower is better", "Opponent-adjusted points allowed per 100 possessions."),
        ("Overall rating", row.get(f"{prefix} AdjNet"), "higher is better", "Offense rating minus defense rating."),
        ("Schedule strength", row.get(f"V1.1 {prefix} D1 SOS", row.get(f"{prefix} SOS")), "higher = tougher", "How difficult the team's Division I schedule has been."),
        ("Points / game", ppg, "pregame average", "Average points scored per game before this matchup."),
        ("Points allowed / game", ppga, "pregame average", "Average points allowed per game before this matchup."),
    ]
    for col, (label, value, foot, tip) in zip(cols, metrics):
        with col: metric_card(label, fmt_num(value, 1), foot, tip)
    if pd.isna(pd.to_numeric(ppg, errors="coerce")) or pd.isna(pd.to_numeric(ppga, errors="coerce")):
        st.caption("Points-per-game averages are blank until the production board publishes true pregame values. Projected scores are never substituted for them.")

    st.markdown('<div class="section-title">Head-to-head profile</div>', unsafe_allow_html=True)
    st.markdown(team_profile_pair_html(row, focus_team=team), unsafe_allow_html=True)
    st.markdown(matchup_battle_html(row, focus_team=team), unsafe_allow_html=True)

    st.markdown('<div class="section-title">Why the model likes its pick — and what could go wrong</div>', unsafe_allow_html=True)
    if model_pick != team:
        st.info(f"The current model pick is {model_pick}. The reasons below explain that selection; use the team comparison above to see how {team} could outperform it.")
    st.markdown(evidence_html(row), unsafe_allow_html=True)
    st.markdown(market_context_html(row), unsafe_allow_html=True)
    st.plotly_chart(team_comparison_chart(row), use_container_width=True)

    st.markdown('<div class="section-title">Slate game context</div>', unsafe_allow_html=True)
    st.dataframe(format_board_for_table(rows), use_container_width=True, hide_index=True)

def render_performance_lab(records: list[dict[str, Any]]) -> None:
    st.markdown('<div class="cbb-kicker">HOW THE MODEL HAS PERFORMED</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Performance Lab</div>', unsafe_allow_html=True)
    st.markdown('<div class="firewall-note"><strong>Results only:</strong> this page measures past predictions. It never changes future predictions.</div>', unsafe_allow_html=True)
    graded_records = [r for r in records if r.get("grading_json")]
    champion_records = [r for r in graded_records if str(r.get("model_version") or "").upper() == "1.1.3B"]
    scoped = champion_records if champion_records else graded_records
    scope_label = "V1.1.3B production model" if champion_records else "Historical published archive (production-model results not yet published)"
    st.caption(scope_label)
    agg = aggregate_metrics(scoped)
    if not agg.get("games"):
        st.info("No graded games are available yet.")
        return

    cols = st.columns(4)
    with cols[0]: metric_card("Games graded", f"{int(agg.get('games',0)):,}", "Division I matchups", "Games where both teams are Division I and an official final score was available.")
    with cols[1]: metric_card("Winner accuracy", fmt_pct(agg.get("winner_accuracy")), "How often the picked team won")
    with cols[2]: metric_card("Average margin miss", fmt_num(agg.get("margin_mae"), 2, " pts"), "Lower is better", "Average number of points the projected winning margin missed the actual final margin by.")
    with cols[3]: metric_card("Average total-points miss", fmt_num(agg.get("total_mae"), 2, " pts"), "Lower is better", "Average number of points the projected combined score missed the actual combined score by.")

    with st.expander("Advanced probability checks", expanded=False):
        st.caption("These are technical ways to test whether the model's confidence percentages are trustworthy. Lower is better for both.")
        c1, c2 = st.columns(2)
        with c1: metric_card("Probability error (Brier score)", fmt_num(agg.get("brier"), 3), "Lower is better", "Measures how close predicted win probabilities were to actual results. Confident wrong picks are penalized.")
        with c2: metric_card("Confidence penalty (log loss)", fmt_num(agg.get("log_loss"), 3), "Lower is better", "Penalizes incorrect predictions more heavily when the model was very confident.")

    hist = history_frame(scoped)
    buckets = confidence_buckets(scoped)
    topk = top_k_summary(scoped)
    if not hist.empty:
        st.plotly_chart(performance_trend(hist), use_container_width=True)
    c1, c2 = st.columns([1.35, 1])
    with c1:
        if not buckets.empty:
            st.plotly_chart(calibration_chart(buckets), use_container_width=True)
    with c2:
        st.markdown('<div class="section-title">How the strongest picks performed</div>', unsafe_allow_html=True)
        if not topk.empty:
            display = topk.copy()
            display["Accuracy"] = display["Accuracy"].map(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
            st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Past slates</div>', unsafe_allow_html=True)
    if not hist.empty:
        columns = [c for c in ["Slate Date", "Games", "Winner Accuracy", "Margin MAE", "Total MAE"] if c in hist.columns]
        display_hist = hist[columns].copy().rename(columns={"Margin MAE":"Average Margin Miss", "Total MAE":"Average Total Miss"})
        if "Winner Accuracy" in display_hist.columns:
            display_hist["Winner Accuracy"] = display_hist["Winner Accuracy"].map(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
        st.dataframe(display_hist.sort_values("Slate Date", ascending=False), use_container_width=True, hide_index=True)

def render_model_guide() -> None:
    st.markdown('<div class="cbb-kicker">HOW TO READ THE SITE</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Plain-English Guide</div>', unsafe_allow_html=True)
    st.markdown(
        """
The site is built to answer four simple questions: **Who does the model like? By how much? Why? What could go wrong?**

**Model spread** — the point spread implied by the model's projected score. A negative number means the selected team is favored by that many points.

**Model-implied odds** — American odds that match the model's win probability. These are **not** sportsbook odds.

**Data confidence** — a 0–100 score for how complete and reliable the inputs are. Higher is better.

**Player status** — whether player availability was verified before the game. If it says “not verified,” late injury or lineup news is a meaningful risk.

**Offense rating** — opponent-adjusted scoring efficiency. Higher is better.

**Defense rating** — opponent-adjusted points allowed. Lower is better.

**Overall rating** — offense rating minus defense rating. Higher is better.

**Schedule strength** — how difficult the team's Division I schedule has been. Higher means tougher competition.

**Typical margin swing** — how unpredictable the game's final margin is around the projection. Bigger means more uncertainty.

**Sportsbook comparison** — shown only when a pregame sportsbook line was saved. It is display-only and never changes the production prediction.

**ML** — moneyline / straight-up winner. The model gets an ML win when it picked the team that won the game.

**Spread** — graded only against a saved pregame or taken sportsbook spread. The closing line is tracked separately and never substituted for the line that was actually available.
        """
    )
    st.markdown('<div class="section-title">Why some technical metrics are hidden</div>', unsafe_allow_html=True)
    st.markdown(
        """
The public cards intentionally hide development terminology, raw model field names and statistical abbreviations that do not help a bettor make a quick decision. Technical probability checks such as Brier score and log loss remain available inside the **Advanced probability checks** section of the Performance Lab, with definitions.
        """
    )

def render_admin_studio(store: SupabaseSlateStore | None, access, records: list[dict[str, Any]]) -> None:
    st.markdown('<div class="cbb-kicker">OWNER WORKFLOW</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Publishing Studio</div>', unsafe_allow_html=True)
    st.markdown('<div class="intel-callout"><strong>Admin-only workflow.</strong> Uploads remain private to this session until you explicitly publish. Public visitors never receive file-upload controls.</div>', unsafe_allow_html=True)
    if store is None:
        st.error("Supabase is not configured. Add the database secrets before publishing.")
        return
    if not access.authorized:
        st.error("This authenticated account is not authorized to publish.")
        return

    board_tab, grade_tab, health_tab = st.tabs(["Publish Board", "Publish Grading", "Storage Health"])
    actor = audit_actor(access.email)

    with board_tab:
        st.markdown("#### Publish a CBB production / compatible historical decision board")
        board_upload = st.file_uploader("CBB decision-board CSV", type=["csv"], key="admin_board_upload")
        if board_upload is not None:
            try:
                candidate, report = normalize_board(read_csv(board_upload))
                st.success(f"Validated V{report.model_version} • {report.slate_date} • {report.rows} games • {report.d1_games} Division I games")
                st.dataframe(format_board_for_table(candidate.head(20)), use_container_width=True, hide_index=True)
                confirm = st.checkbox("I reviewed this board and authorize publication.", key="confirm_board_publish")
                if st.button("Publish decision board", type="primary", disabled=not confirm):
                    with st.spinner("Publishing board..."):
                        saved = store.publish_board(candidate, report, board_upload.name, actor)
                    st.success(f"Published {report.slate_date} revision {saved.get('revision',1)}.")
                    st.cache_data.clear()
                    st.rerun()
            except (DataValidationError, StorageOperationError, StorageConfigurationError) as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Board publication failed safely: {type(exc).__name__}")

    with grade_tab:
        st.markdown("#### Publish completed-slate grading")
        grade_upload = st.file_uploader("CBB graded-board CSV", type=["csv"], key="admin_grade_upload")
        if grade_upload is not None:
            try:
                graded, report = normalize_graded_board(read_csv(grade_upload))
                eligible = int(graded.get("Primary Evaluation Eligible", graded.get("D1 Evaluation Eligible", pd.Series(False, index=graded.index))).fillna(False).astype(bool).sum())
                st.success(f"Validated grading • {report.slate_date} • {eligible} primary evaluation games")
                preview_cols = [c for c in ["Rank","Away Team","Home Team","Model Pick","Actual Winner","Model Winner Correct","Absolute Margin Error","V1.0.1 Baseline Winner Correct","V1.0.1 Baseline Absolute Margin Error"] if c in graded.columns]
                st.dataframe(graded[preview_cols].head(30), use_container_width=True, hide_index=True)
                confirm = st.checkbox("I reviewed these final scores and authorize grading publication.", key="confirm_grade_publish")
                if st.button("Publish grading", type="primary", disabled=not confirm):
                    with st.spinner("Publishing grading..."):
                        store.publish_grading(graded, report, grade_upload.name, actor)
                    st.success(f"Published grading for {report.slate_date}.")
                    st.cache_data.clear()
                    st.rerun()
            except (DataValidationError, StorageOperationError, StorageConfigurationError) as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Grading publication failed safely: {type(exc).__name__}")

    with health_tab:
        st.markdown("#### Storage access")
        try:
            store.check_access(admin=False)
            st.success("Public read path: ready")
        except Exception as exc:
            st.error(f"Public read path: {exc}")
        try:
            store.check_access(admin=True)
            st.success("Admin write client: ready")
        except Exception as exc:
            st.error(f"Admin write path: {exc}")
        st.caption(f"Published records visible to the app: {len(records)}. Secret values are never rendered here.")


@st.cache_data(ttl=30, show_spinner=False)
def cached_record_list(_store: SupabaseSlateStore | None) -> list[dict[str, Any]]:
    if _store is None:
        return []
    return _store.list_records(limit=120)


store, store_error = make_store()
user = current_user_dict()
access = evaluate_admin_identity(user, str(secret("ADMIN_EMAIL", "") or ""))

records: list[dict[str, Any]] = []
if store is not None:
    try:
        records = cached_record_list(store)
        store_error = None
    except Exception as exc:
        store_error = str(exc)
        records = []

# Sidebar mirrors the HR dashboard's compact navigation while using a basketball-orange identity.
with st.sidebar:
    st.markdown('<div class="cbb-kicker">CBB MODEL</div>', unsafe_allow_html=True)
    st.caption("Public dashboard · read-only")
    if records:
        dates = [str(r.get("slate_date")) for r in records if r.get("slate_date")]
        selected_date = st.selectbox(
            "Published slate",
            dates,
            index=0,
            help="Defaults to the most recently published decision board, regardless of game date.",
        )
    else:
        selected_date = None

    public_pages = ["Today's Board", "Matchup Explorer", "Team Intelligence", "Performance Lab", "Model Guide"]
    pages = public_pages + (["Admin Studio"] if access.authorized else [])
    page = st.radio("Navigate", pages, label_visibility="collapsed")

    st.divider()
    if access.authenticated:
        st.caption("Authenticated session")
        if access.authorized:
            st.success("Owner access enabled")
        else:
            st.info("Signed in · read-only")
        if st.button("Sign out", use_container_width=True):
            st.logout()
    elif auth_is_configured():
        st.caption("Owner publishing")
        if st.button("Admin sign in", use_container_width=True):
            st.login("google")
    else:
        st.caption("Google OIDC not configured yet")

    if store_error:
        st.caption("Publishing storage unavailable")
    st.markdown(f'<div class="small-muted" style="margin-top:1rem">Betting Intelligence v{APP_VERSION}</div>', unsafe_allow_html=True)

record: dict[str, Any] | None = None
if selected_date and records:
    record = next((r for r in records if str(r.get("slate_date")) == selected_date), None)

board = pd.DataFrame()
report = None
if record:
    try:
        board, report = normalize_board(SupabaseSlateStore.board_frame(record))
        grading = SupabaseSlateStore.grading_frame(record)
        if grading is not None and not grading.empty:
            board = attach_grading(board, grading)
    except Exception as exc:
        st.error(f"The published board could not be validated: {exc}")

if page == "Admin Studio":
    render_admin_studio(store, access, records)
elif board.empty or report is None:
    render_empty_state(store_error)
    if page == "Model Guide":
        render_model_guide()
else:
    render_header(report, record)
    if page == "Today's Board":
        render_board(board, report)
    elif page == "Matchup Explorer":
        render_matchup_explorer(board)
    elif page == "Team Intelligence":
        render_team_intelligence(board)
    elif page == "Performance Lab":
        render_performance_lab(records)
    elif page == "Model Guide":
        render_model_guide()

st.markdown(
    f'<div class="small-muted" style="margin:2rem 0 .5rem">CBB Model Betting Intelligence v{APP_VERSION} • Public interface read-only • Independent model remains market-blind</div>',
    unsafe_allow_html=True,
)
