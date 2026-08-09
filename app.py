from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from cbb_dashboard.charts import (
    calibration_chart,
    challenger_comparison_chart,
    confidence_chart,
    performance_trend,
    team_comparison_chart,
)
from cbb_dashboard.data import (
    DataValidationError,
    board_table,
    normalize_board,
    normalize_graded_board,
    read_csv,
)
from cbb_dashboard.intelligence import evidence_html, game_card_grid_html, game_card_html, translation_direction
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
APP_VERSION = "1.1"

st.set_page_config(
    page_title="CBB Model | Intelligence Terminal",
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


def metric_card(label: str, value: str, foot: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-shell">
          <div class="metric-label">{esc(label)}</div>
          <div class="metric-value">{esc(value)}</div>
          <div class="metric-foot">{esc(foot)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_strip(report, board: pd.DataFrame) -> None:
    d1_pct = (report.d1_games / report.rows) if report.rows else 0.0
    translation_games = int((board["_translation"].abs() >= 0.05).sum())
    training = pd.to_numeric(board.get("Schedule Translation Training Games"), errors="coerce")
    train_text = f"{int(training.max()):,} prior games" if training.notna().any() else "not reported"
    verified = float(board["_availability_verified"].mean()) if len(board) else 0.0
    quality = pd.to_numeric(board.get("Data Quality"), errors="coerce").mean()
    html = f"""
    <div class="status-strip">
      <div class="status-item"><div class="status-top"><span class="status-dot fresh"></span>Engine</div><div class="status-value">V{esc(report.model_version)}</div><div class="status-detail">Schedule-translation challenger</div></div>
      <div class="status-item"><div class="status-top"><span class="status-dot info"></span>D-I cohort</div><div class="status-value">{report.d1_games}/{report.rows} games</div><div class="status-detail">{d1_pct:.0%} primary evaluation coverage</div></div>
      <div class="status-item"><div class="status-top"><span class="status-dot info"></span>Schedule layer</div><div class="status-value">{translation_games} adjusted</div><div class="status-detail">{esc(train_text)} in largest fitted window</div></div>
      <div class="status-item"><div class="status-top"><span class="status-dot {'fresh' if verified >= .99 else 'warn'}"></span>Availability</div><div class="status-value">{verified:.0%} verified</div><div class="status-detail">Display flag; model uses only supplied availability</div></div>
      <div class="status-item"><div class="status-top"><span class="status-dot {'fresh' if pd.notna(quality) and quality >= 65 else 'warn'}"></span>Data quality</div><div class="status-value">{fmt_num(quality,0)}/100</div><div class="status-detail">Mean slate quality score</div></div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


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
    st.markdown('<div class="cbb-kicker">COLLEGE BASKETBALL INTELLIGENCE</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="cbb-title">{BRAND} <span style="color:#f97316">//</span> INTELLIGENCE TERMINAL</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="cbb-subtitle">{esc(report.slate_date)} &nbsp;•&nbsp; Challenger {esc(report.model_version)} &nbsp;•&nbsp; {esc(publication)}</div>',
        unsafe_allow_html=True,
    )


def render_empty_state(store_error: str | None) -> None:
    st.markdown('<div class="cbb-kicker">COLLEGE BASKETBALL INTELLIGENCE</div>', unsafe_allow_html=True)
    st.markdown('<div class="cbb-title">CBB MODEL <span style="color:#f97316">//</span> INTELLIGENCE TERMINAL</div>', unsafe_allow_html=True)
    st.markdown('<div class="cbb-subtitle">Public read-only analytics interface • No slate is currently published.</div>', unsafe_allow_html=True)
    if store_error:
        st.info("Publishing storage has not been configured for this deployment yet. Public upload controls remain disabled.")
    else:
        st.info("No published CBB V1.1 decision board is available yet. Sign in as the authorized owner to publish the first slate.")
    st.markdown(
        '<div class="firewall-note"><strong>Model firewall:</strong> the website reads published model output. It does not rerun, rescore, or modify the independent CBB prediction engine.</div>',
        unsafe_allow_html=True,
    )


def format_board_for_table(board: pd.DataFrame) -> pd.DataFrame:
    out = board_table(board)
    for c in ["Win Probability", "V1.0.1 Baseline Win Probability"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").map(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
    for c in ["Fair Spread", "V1.0.1 Baseline Fair Spread", "Schedule Translation Margin Adj"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").map(lambda x: f"{x:+.1f}" if pd.notna(x) else "—")
    return out


def apply_board_filters(board: pd.DataFrame) -> pd.DataFrame:
    st.markdown('<div class="section-title">Board filters</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    teams = sorted(set(board["Home Team"].astype(str)).union(set(board["Away Team"].astype(str))))
    with c1:
        selected_teams = st.multiselect("Teams", teams, placeholder="All teams")
    with c2:
        cohort = st.selectbox("Evaluation cohort", ["All games", "D-I vs D-I only", "Non-primary only"])
    with c3:
        confidence_floor = st.slider("Minimum win probability", 50, 95, 50, 1)
    with c4:
        only_changed = st.toggle("V1.1 pick changes only", value=False)
    filtered = board.copy()
    if selected_teams:
        filtered = filtered[filtered["Home Team"].isin(selected_teams) | filtered["Away Team"].isin(selected_teams)]
    if cohort == "D-I vs D-I only":
        filtered = filtered[filtered["_is_d1"]]
    elif cohort == "Non-primary only":
        filtered = filtered[~filtered["_is_d1"]]
    filtered = filtered[filtered["_win_prob"] >= confidence_floor / 100.0]
    if only_changed:
        filtered = filtered[filtered["_pick_changed"]]
    return filtered


def render_board(board: pd.DataFrame, report) -> None:
    status_strip(report, board)
    d1 = board[board["_is_d1"]].copy()
    strongest = board.sort_values("_win_prob", ascending=False).iloc[0] if len(board) else None
    cols = st.columns(5)
    with cols[0]: metric_card("Games", f"{len(board)}", f"{report.d1_games} D-I vs D-I")
    with cols[1]: metric_card("Strongest pick", str(strongest.get("Model Pick")) if strongest is not None else "—", fmt_pct(strongest.get("Win Probability")) if strongest is not None else "")
    with cols[2]: metric_card("Neutral court", f"{int(board['_neutral'].sum())}", "Tournament / neutral-site flag")
    with cols[3]: metric_card("Pick changes", f"{int(board['_pick_changed'].sum())}", "Versus frozen V1.0.1")
    with cols[4]: metric_card("Avg translation", f"{board['_translation'].abs().mean():.1f} pts", "Absolute schedule adjustment")

    for warning in report.warnings:
        st.warning(warning, icon="⚠️")

    st.markdown('<div class="section-title">Priority board</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-note">Ranked game cards preserve the HR site’s quick-scan format, redesigned around score, spread, pace and team-strength context.</div>', unsafe_allow_html=True)
    scope = st.segmented_control("Card depth", ["Top 10", "Top 25", "Top 50", "All"], default="Top 10", label_visibility="collapsed")
    n = {"Top 10": 10, "Top 25": 25, "Top 50": 50, "All": len(board)}.get(scope, 10)
    st.markdown(game_card_grid_html(board.head(n)), unsafe_allow_html=True)

    filtered = apply_board_filters(board)
    st.markdown(f'<div class="section-title">Full decision board ({len(filtered)})</div>', unsafe_allow_html=True)
    st.dataframe(format_board_for_table(filtered), use_container_width=True, hide_index=True, height=min(700, 70 + 35 * max(4, len(filtered))))

    if len(d1) >= 2:
        st.markdown('<div class="section-title">Confidence separation</div>', unsafe_allow_html=True)
        st.plotly_chart(confidence_chart(d1, top_n=min(25, len(d1))), use_container_width=True)


def matchup_label(row: pd.Series) -> str:
    marker = " · N" if bool(row.get("Neutral Site", False)) else ""
    return f"#{int(row.get('_rank', 0))} {row.get('Away Team')} vs {row.get('Home Team')}{marker}"


def comparison_html(row: pd.Series) -> str:
    return f"""
    <div class="compare-shell">
      <div class="compare-side"><div class="compare-title">Frozen V1.0.1 baseline</div><div class="compare-main">{esc(row.get('V1.0.1 Baseline Pick','—'))} {fmt_spread(row.get('V1.0.1 Baseline Fair Spread'))}</div><div class="compare-sub">{fmt_pct(row.get('V1.0.1 Baseline Win Probability'))} win probability</div></div>
      <div class="compare-arrow">→</div>
      <div class="compare-side primary"><div class="compare-title">V1.1 challenger</div><div class="compare-main">{esc(row.get('Model Pick','—'))} {fmt_spread(row.get('Fair Spread'))}</div><div class="compare-sub">{fmt_pct(row.get('Win Probability'))} • {esc(translation_direction(row))}</div></div>
    </div>
    """


def render_matchup_explorer(board: pd.DataFrame) -> None:
    st.markdown('<div class="cbb-kicker">GAME-LEVEL EXPLAINABILITY</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Matchup Explorer</div>', unsafe_allow_html=True)
    labels = {matchup_label(row): idx for idx, row in board.iterrows()}
    choice = st.selectbox("Select a matchup", list(labels.keys()))
    row = board.loc[labels[choice]]
    st.markdown(game_card_html(row), unsafe_allow_html=True)
    st.markdown(comparison_html(row), unsafe_allow_html=True)
    st.markdown(evidence_html(row), unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(team_comparison_chart(row), use_container_width=True)
    with c2:
        st.plotly_chart(challenger_comparison_chart(row), use_container_width=True)

    st.markdown('<div class="section-title">Simulation and uncertainty</div>', unsafe_allow_html=True)
    sim = st.columns(5)
    with sim[0]: metric_card("Home margin P10", fmt_num(row.get("Home Margin P10"), 1), "10th percentile")
    with sim[1]: metric_card("Expected home margin", fmt_num(pd.to_numeric(row.get("Projected Home Score"), errors="coerce") - pd.to_numeric(row.get("Projected Away Score"), errors="coerce"), 1), "Projected score gap")
    with sim[2]: metric_card("Home margin P90", fmt_num(row.get("Home Margin P90"), 1), "90th percentile")
    with sim[3]: metric_card("Margin SD", fmt_num(row.get("Margin SD"), 1), "Simulation spread")
    with sim[4]: metric_card("Projected total", fmt_num(row.get("Projected Total"), 1), "Market-blind total")

    st.markdown(
        f'<div class="intel-callout"><strong>Schedule translation:</strong> {esc(str(row.get("Schedule Translation Status") or "Not reported"))}. '
        f'Home D-I SOS {fmt_num(row.get("V1.1 Home D1 SOS"),1)} vs away {fmt_num(row.get("V1.1 Away D1 SOS"),1)}; '
        f'net V1.1 margin adjustment {fmt_num(row.get("Schedule Translation Margin Adj"),1," pts")}.</div>',
        unsafe_allow_html=True,
    )


def team_rows(board: pd.DataFrame, team: str) -> pd.DataFrame:
    return board[(board["Home Team"].astype(str) == team) | (board["Away Team"].astype(str) == team)].copy()


def render_team_intelligence(board: pd.DataFrame) -> None:
    st.markdown('<div class="cbb-kicker">TEAM PROFILE</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Team Intelligence</div>', unsafe_allow_html=True)
    teams = sorted(set(board["Home Team"].astype(str)).union(set(board["Away Team"].astype(str))))
    team = st.selectbox("Select team", teams)
    rows = team_rows(board, team)
    row = rows.sort_values("_rank").iloc[0]
    home = str(row.get("Home Team")) == team
    prefix = "Home" if home else "Away"
    opponent = row.get("Away Team" if home else "Home Team")
    st.markdown(f'<div class="intel-callout"><strong>{esc(team)}</strong> vs {esc(opponent)} • {"neutral court" if bool(row.get("Neutral Site",False)) else "scheduled site"} • model pick: {esc(row.get("Model Pick"))}</div>', unsafe_allow_html=True)
    cols = st.columns(6)
    metrics = [
        ("AdjO", row.get(f"{prefix} AdjO"), "points / 100"),
        ("AdjD", row.get(f"{prefix} AdjD"), "points allowed / 100"),
        ("AdjNet", row.get(f"{prefix} AdjNet"), "efficiency margin"),
        ("D-I SOS", row.get(f"V1.1 {prefix} D1 SOS", row.get(f"{prefix} SOS")), "national schedule"),
        ("Matchup adj", row.get(f"{prefix} Matchup Adj /100"), "four-factor fit"),
        ("Availability adj", row.get(f"{prefix} Availability Adj"), "points"),
    ]
    for col, (label, value, foot) in zip(cols, metrics):
        with col: metric_card(label, fmt_num(value, 1), foot)
    st.plotly_chart(team_comparison_chart(row), use_container_width=True)
    st.markdown('<div class="section-title">Game context</div>', unsafe_allow_html=True)
    st.dataframe(format_board_for_table(rows), use_container_width=True, hide_index=True)


def render_performance_lab(records: list[dict[str, Any]]) -> None:
    st.markdown('<div class="cbb-kicker">WALK-FORWARD EVIDENCE</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Performance Laboratory</div>', unsafe_allow_html=True)
    st.markdown('<div class="firewall-note"><strong>Observational only:</strong> grading and challenger-vs-baseline analysis never feed back into a published prediction. V1.1 remains market-blind.</div>', unsafe_allow_html=True)
    agg = aggregate_metrics(records)
    if not agg.get("games"):
        st.info("No V1.1 graded slates have been published yet. Upload a challenger graded board in Admin Studio after the games are final.")
        return
    cols = st.columns(6)
    with cols[0]: metric_card("D-I games", f"{int(agg.get('games',0)):,}", "Primary cohort")
    with cols[1]: metric_card("Winner accuracy", fmt_pct(agg.get("winner_accuracy")), "V1.1")
    with cols[2]: metric_card("Brier", fmt_num(agg.get("brier"), 3), "Lower is better")
    with cols[3]: metric_card("Margin MAE", fmt_num(agg.get("margin_mae"), 2), "Points")
    with cols[4]: metric_card("Baseline MAE", fmt_num(agg.get("baseline_margin_mae"), 2), "V1.0.1")
    with cols[5]: metric_card("MAE improvement", fmt_num(agg.get("margin_mae_improvement"), 2), "Positive favors V1.1")

    hist = history_frame(records)
    buckets = confidence_buckets(records)
    topk = top_k_summary(records)
    if not hist.empty:
        st.plotly_chart(performance_trend(hist), use_container_width=True)
    c1, c2 = st.columns([1.35, 1])
    with c1:
        if not buckets.empty:
            st.plotly_chart(calibration_chart(buckets), use_container_width=True)
    with c2:
        st.markdown('<div class="section-title">Top-K separation</div>', unsafe_allow_html=True)
        if not topk.empty:
            display = topk.copy()
            display["Accuracy"] = display["Accuracy"].map(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
            st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Slate archive</div>', unsafe_allow_html=True)
    display_hist = hist.copy()
    if not display_hist.empty:
        for c in ["Winner Accuracy", "V1.0.1 Winner Accuracy"]:
            if c in display_hist.columns:
                display_hist[c] = display_hist[c].map(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
        st.dataframe(display_hist.sort_values("Slate Date", ascending=False), use_container_width=True, hide_index=True)


def render_model_guide() -> None:
    st.markdown('<div class="cbb-kicker">MODEL DOCUMENTATION</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">V1.1 Intelligence Guide</div>', unsafe_allow_html=True)
    st.markdown(
        """
**Prediction hierarchy.** V1.1 starts from the independent opponent-adjusted team-strength engine, pace and Four Factors, then applies the challenger’s leakage-safe D-I schedule-translation layer to the projected margin. The score distribution remains the source of the win probability, fair moneyline and fair spread.

**Frozen baseline.** Every challenger board carries the same-run V1.0.1 prediction beside V1.1. The terminal exposes changes rather than hiding them, so the historical test remains auditable.

**Primary cohort.** D-I vs D-I games are the primary performance population. Non-D-I games can remain visible but do not drive the main evaluation metrics.

**Confidence Score.** The 50–100 confidence field is an ordinal decision-support score, not a probability. Use `Win Probability` for probabilistic interpretation.

**Availability.** Player availability is shown explicitly. Historical slates with unverified availability should be interpreted as primarily testing the team-strength engine.

**Market firewall.** This release contains no sportsbook odds, betting splits, line movement, edge ranking or +EV logic. Those belong to the later Market Terminal after independent challenger validation.
        """
    )
    st.markdown('<div class="section-title">Reading a game card</div>', unsafe_allow_html=True)
    st.markdown(
        """
The card headline answers **who**, **by how much**, and **with what probability**. The scoreboard gives the model’s expected score. `Fair Spread` is expressed from the model pick’s perspective. `Projected Total` and pace describe the expected game environment. The frozen-baseline strip shows whether schedule translation merely widened/narrowed the margin or actually changed the side.
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
        st.markdown("#### Publish a V1.1 challenger decision board")
        board_upload = st.file_uploader("V1.1 decision-board CSV", type=["csv"], key="admin_board_upload")
        if board_upload is not None:
            try:
                candidate, report = normalize_board(read_csv(board_upload))
                st.success(f"Validated V{report.model_version} • {report.slate_date} • {report.rows} games • {report.d1_games} primary D-I games")
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
        grade_upload = st.file_uploader("V1.1 graded-board CSV", type=["csv"], key="admin_grade_upload")
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
        selected_date = st.selectbox("Published slate", dates, index=0)
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
    st.markdown(f'<div class="small-muted" style="margin-top:1rem">Intelligence Terminal v{APP_VERSION}</div>', unsafe_allow_html=True)

record: dict[str, Any] | None = None
if selected_date and records:
    record = next((r for r in records if str(r.get("slate_date")) == selected_date), None)

board = pd.DataFrame()
report = None
if record:
    try:
        board, report = normalize_board(SupabaseSlateStore.board_frame(record))
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
    f'<div class="small-muted" style="margin:2rem 0 .5rem">CBB Model Dashboard v{APP_VERSION} • Public interface read-only • Independent model remains market-blind</div>',
    unsafe_allow_html=True,
)
