from __future__ import annotations

import html
import math


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


def fmt_num(value: object, digits: int = 1, suffix: str = "") -> str:
    try:
        number = float(value)
        if math.isnan(number):
            return "—"
        return f"{number:.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return "—"


def fmt_pct(value: object, digits: int = 1) -> str:
    try:
        number = float(value)
        if math.isnan(number):
            return "—"
        if abs(number) <= 1.000001:
            number *= 100.0
        return f"{number:.{digits}f}%"
    except (TypeError, ValueError):
        return "—"


def fmt_odds(value: object) -> str:
    try:
        number = float(value)
        if math.isnan(number):
            return "—"
        number = int(round(number))
        return f"+{number}" if number > 0 else str(number)
    except (TypeError, ValueError):
        return "—"


def fmt_spread(value: object, team: str = "") -> str:
    try:
        number = float(value)
        if math.isnan(number):
            return "—"
        prefix = team.strip() + " " if team else ""
        return f"{prefix}{number:+.1f}"
    except (TypeError, ValueError):
        return "—"


GLOBAL_CSS = r"""
<style>
:root {
  --bg:#10090c;
  --bg-2:#160d10;
  --panel:#1b1115;
  --panel-2:#25171b;
  --line:rgba(251,146,60,.18);
  --line-soft:rgba(231,203,188,.12);
  --text:#fff7ed;
  --muted:#b6a39a;
  --accent:#f97316;
  --accent-2:#2dd4bf;
  --gold:#fbbf24;
  --green:#4ade80;
  --red:#fb7185;
  --purple:#c084fc;
}

.stApp {
  background:
    radial-gradient(circle at 8% -10%, rgba(124,45,18,.46) 0%, rgba(37,18,23,.28) 30%, transparent 52%),
    radial-gradient(circle at 96% 6%, rgba(45,212,191,.10) 0%, transparent 28%),
    linear-gradient(180deg, var(--bg-2) 0%, #0d080a 52%, #080507 100%);
  color:var(--text);
}
[data-testid="stSidebar"] { background:#100b0d; border-right:1px solid var(--line-soft); }
[data-testid="stHeader"] { background:rgba(8,5,7,.78); }
.block-container { padding-top:1.65rem; max-width:1520px; }

.cbb-kicker { color:var(--accent); font-size:.78rem; letter-spacing:.18em; font-weight:900; text-transform:uppercase; }
.cbb-title { font-size:clamp(2rem,4vw,3.55rem); line-height:1; margin:.3rem 0 .45rem; font-weight:950; letter-spacing:-.045em; color:#fffaf5; }
.cbb-subtitle { color:var(--muted); font-size:.98rem; margin-bottom:1.25rem; }
.section-title { font-size:1.16rem; font-weight:900; margin:1.35rem 0 .72rem; letter-spacing:-.01em; }
.section-note { color:var(--muted); font-size:.86rem; margin-top:-.42rem; margin-bottom:.8rem; }
.small-muted { color:var(--muted); font-size:.75rem; }

.metric-shell { background:linear-gradient(180deg,rgba(37,23,27,.96),rgba(24,14,18,.96)); border:1px solid var(--line-soft); border-radius:16px; padding:14px 15px; min-height:90px; box-shadow:0 10px 26px rgba(0,0,0,.12); }
.metric-label { color:var(--muted); font-size:.70rem; text-transform:uppercase; letter-spacing:.09em; font-weight:800; }
.metric-value { font-size:1.52rem; font-weight:950; color:var(--text); margin-top:5px; }
.metric-foot { color:var(--muted); font-size:.70rem; margin-top:2px; }

.status-strip { display:grid; grid-template-columns:repeat(auto-fit,minmax(175px,1fr)); gap:8px; margin:2px 0 14px; }
.status-item { background:rgba(31,18,23,.86); border:1px solid var(--line-soft); border-radius:12px; padding:10px 11px; min-width:0; }
.status-top { display:flex; align-items:center; gap:6px; color:#c4b2aa; font-size:.61rem; font-weight:850; text-transform:uppercase; letter-spacing:.07em; }
.status-dot { width:7px; height:7px; border-radius:50%; display:inline-block; flex:0 0 auto; }
.status-dot.fresh { background:var(--green); box-shadow:0 0 10px rgba(74,222,128,.45); }
.status-dot.info { background:var(--accent-2); box-shadow:0 0 10px rgba(45,212,191,.35); }
.status-dot.warn { background:var(--gold); box-shadow:0 0 10px rgba(251,191,36,.35); }
.status-dot.risk { background:var(--red); box-shadow:0 0 10px rgba(251,113,133,.35); }
.status-value { color:#fff8f2; font-size:.78rem; font-weight:900; margin-top:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.status-detail { color:#8f7c75; font-size:.59rem; margin-top:2px; line-height:1.35; }

.game-card-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; align-items:start; }
.game-card { background:linear-gradient(145deg,rgba(38,22,27,.98),rgba(19,11,15,.98)); border:1px solid var(--line-soft); border-radius:18px; padding:17px 18px 16px; box-shadow:0 14px 34px rgba(0,0,0,.16); min-width:0; }
.game-card.strong { border-color:rgba(249,115,22,.42); }
.game-card.tossup { border-color:rgba(45,212,191,.30); }
.game-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; }
.rank-pill { font-size:.72rem; line-height:1; font-weight:950; color:#180b06; background:var(--accent); padding:7px 8px; border-radius:9px; display:inline-block; }
.game-time { color:var(--muted); font-size:.69rem; margin-top:7px; }
.prob { font-size:1.65rem; font-weight:950; color:var(--accent-2); text-align:right; line-height:1; }
.prob-label { color:var(--muted); text-align:right; font-size:.62rem; text-transform:uppercase; letter-spacing:.08em; margin-top:3px; }
.model-pick { text-align:right; color:#fff; font-size:.82rem; font-weight:900; margin-top:6px; }

.scoreboard { margin:14px 0 10px; border:1px solid var(--line-soft); border-radius:14px; overflow:hidden; background:rgba(255,255,255,.018); }
.team-row { display:grid; grid-template-columns:minmax(0,1fr) 88px; align-items:center; gap:10px; padding:10px 12px; border-bottom:1px solid rgba(231,203,188,.08); }
.team-row:last-child { border-bottom:0; }
.team-row.pick { background:linear-gradient(90deg,rgba(249,115,22,.10),transparent 66%); }
.team-name { color:#f8eee8; font-weight:900; font-size:1rem; line-height:1.15; }
.team-tag { color:var(--accent); font-size:.58rem; text-transform:uppercase; letter-spacing:.08em; font-weight:900; margin-left:6px; }
.score { color:#fffaf5; font-size:1.35rem; font-weight:950; text-align:right; }

.chip-row { display:flex; flex-wrap:wrap; gap:6px; margin:10px 0; }
.chip { display:inline-flex; align-items:center; padding:5px 8px; border-radius:999px; border:1px solid var(--line-soft); color:#c6b7b0; background:rgba(255,255,255,.024); font-size:.66rem; font-weight:750; }
.chip.orange { color:#ffb27d; border-color:rgba(249,115,22,.30); background:rgba(249,115,22,.08); }
.chip.teal { color:#87eee4; border-color:rgba(45,212,191,.28); background:rgba(45,212,191,.07); }
.chip.green { color:#9af0b6; border-color:rgba(74,222,128,.26); background:rgba(74,222,128,.06); }
.chip.gold { color:#ffdd83; border-color:rgba(251,191,36,.28); background:rgba(251,191,36,.06); }
.chip.red { color:#ff9bad; border-color:rgba(251,113,133,.28); background:rgba(251,113,133,.06); }

.card-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; margin-top:10px; }
.card-stat { background:rgba(255,255,255,.022); border:1px solid rgba(231,203,188,.09); border-radius:10px; padding:8px; min-width:0; }
.card-stat-label { color:var(--muted); font-size:.58rem; text-transform:uppercase; letter-spacing:.06em; }
.card-stat-value { color:#fff8f2; font-size:.84rem; font-weight:900; margin-top:2px; overflow:hidden; text-overflow:ellipsis; }
.baseline-strip { border-top:1px solid rgba(231,203,188,.10); margin-top:11px; padding-top:10px; color:#cdbcb4; font-size:.71rem; line-height:1.45; }
.baseline-strip strong { color:#fff4ec; }
.translation-note { color:#fbb98e; font-weight:800; }

.intel-callout { border:1px solid rgba(249,115,22,.22); background:rgba(249,115,22,.055); border-radius:13px; padding:12px 14px; color:#d9c8bf; font-size:.78rem; line-height:1.5; }
.intel-callout strong { color:#fff8f2; }
.firewall-note { color:#ad9b93; font-size:.70rem; line-height:1.45; border-left:3px solid rgba(45,212,191,.55); padding:8px 10px; background:rgba(45,212,191,.045); border-radius:0 8px 8px 0; margin:10px 0; }
.evidence-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:10px; }
.evidence-box { border:1px solid var(--line-soft); border-radius:12px; padding:11px 12px; background:rgba(255,255,255,.018); }
.evidence-box.positive { border-color:rgba(74,222,128,.20); background:rgba(74,222,128,.035); }
.evidence-box.risk { border-color:rgba(251,113,133,.20); background:rgba(251,113,133,.035); }
.evidence-title { font-size:.66rem; font-weight:950; letter-spacing:.07em; text-transform:uppercase; color:#fff7f0; margin-bottom:7px; }
.evidence-list { margin:0; padding-left:17px; color:#d1c1b8; font-size:.72rem; line-height:1.48; }
.evidence-list li { margin:3px 0; }

.compare-shell { display:grid; grid-template-columns:1fr auto 1fr; align-items:stretch; gap:8px; margin:10px 0; }
.compare-side { border:1px solid var(--line-soft); border-radius:13px; padding:12px; background:rgba(255,255,255,.018); }
.compare-side.primary { border-color:rgba(249,115,22,.30); background:rgba(249,115,22,.04); }
.compare-title { color:var(--muted); font-size:.63rem; text-transform:uppercase; letter-spacing:.08em; font-weight:900; }
.compare-main { color:#fff8f2; font-size:1.1rem; font-weight:950; margin-top:5px; }
.compare-sub { color:#a9958c; font-size:.70rem; margin-top:3px; }
.compare-arrow { align-self:center; color:var(--accent); font-size:1.3rem; font-weight:900; }

div[data-testid="stDataFrame"] { border:1px solid var(--line-soft); border-radius:14px; overflow:hidden; }
.stTabs [data-baseweb="tab-list"] { gap:6px; }
.stTabs [data-baseweb="tab"] { background:#170f12; border:1px solid var(--line-soft); border-radius:10px; padding:8px 14px; }
.stTabs [aria-selected="true"] { background:#2a191d; color:#fff; border-color:rgba(249,115,22,.34); }

@media (max-width:950px) {
  .game-card-grid { grid-template-columns:1fr; }
  .card-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .cbb-title { font-size:2.25rem; }
  .evidence-grid { grid-template-columns:1fr; }
  .compare-shell { grid-template-columns:1fr; }
  .compare-arrow { display:none; }
  .status-strip { grid-template-columns:repeat(2,minmax(0,1fr)); }
}


/* v1.2 Champion Terminal */
.chip.champion { color:#ffe4a3; border-color:rgba(251,191,36,.34); background:linear-gradient(90deg,rgba(251,191,36,.10),rgba(249,115,22,.055)); }
.result-banner { display:grid; grid-template-columns:auto 1fr; grid-template-areas:"final outcomes" "line line"; align-items:center; gap:6px 10px; margin:-4px -4px 13px; padding:9px 10px; border:1px solid rgba(148,163,184,.16); border-radius:12px; background:rgba(255,255,255,.025); }
.result-banner.win { border-color:rgba(74,222,128,.30); background:linear-gradient(90deg,rgba(74,222,128,.095),rgba(74,222,128,.02)); }
.result-banner.sweep { border-color:rgba(251,191,36,.48); background:linear-gradient(90deg,rgba(251,191,36,.15),rgba(249,115,22,.045)); box-shadow:0 0 22px rgba(251,191,36,.055); }
.result-banner.loss { opacity:.86; }
.result-final { grid-area:final; color:#fff6e8; font-size:.68rem; font-weight:950; letter-spacing:.08em; }
.result-outcomes { grid-area:outcomes; display:flex; justify-content:flex-end; gap:6px; flex-wrap:wrap; }
.result-line { grid-area:line; color:#8f7c75; font-size:.58rem; }
.result-pill { display:inline-flex; gap:5px; align-items:center; border-radius:999px; padding:5px 8px; font-size:.62rem; font-weight:900; letter-spacing:.04em; border:1px solid transparent; }
.result-pill.ml-win { color:#08170e; background:#4ade80; border-color:#86efac; }
.result-pill.spread-win { color:#1c1200; background:linear-gradient(90deg,#fbbf24,#f59e0b); border-color:#fde68a; }
.result-pill.loss-pill { color:#ffb1bd; border-color:rgba(251,113,133,.26); background:rgba(251,113,133,.07); }
.result-pill.pending-pill { color:#b6a39a; border-color:rgba(182,163,154,.18); background:rgba(255,255,255,.025); }
.intel-dossier { margin-top:12px; border-top:1px solid var(--line-soft); padding-top:10px; }
.intel-dossier > summary { list-style:none; display:flex; justify-content:space-between; gap:10px; align-items:center; cursor:pointer; color:#ffe9c1; font-size:.70rem; font-weight:900; padding:8px 9px; border-radius:10px; background:rgba(251,191,36,.045); border:1px solid rgba(251,191,36,.14); }
.intel-dossier > summary::-webkit-details-marker { display:none; }
.intel-dossier[open] > summary { border-color:rgba(251,191,36,.34); background:rgba(251,191,36,.075); }
.dossier-body { padding-top:10px; }
.matchup-table { margin-top:10px; border:1px solid var(--line-soft); border-radius:12px; overflow:hidden; background:rgba(255,255,255,.014); }
.matchup-head,.matchup-row { display:grid; grid-template-columns:minmax(130px,.8fr) repeat(2,minmax(85px,1fr)); gap:8px; align-items:center; padding:8px 10px; }
.matchup-head { background:rgba(251,191,36,.045); color:#bda99f; font-size:.62rem; text-transform:uppercase; letter-spacing:.055em; }
.matchup-head strong { color:#fff1d2; text-align:right; overflow:hidden; text-overflow:ellipsis; }
.matchup-row { border-top:1px solid rgba(231,203,188,.07); }
.matchup-label { color:#a9958b; font-size:.64rem; }
.matchup-value { text-align:right; color:#f8eee8; font-size:.70rem; font-weight:850; }
.matchup-value.pick-side { color:#ffe29a; }
.dossier-context-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:7px; margin-top:10px; }
.dossier-context { border:1px solid rgba(231,203,188,.08); border-radius:9px; padding:8px; background:rgba(255,255,255,.018); }
.dossier-context span { display:block; color:#9b877e; font-size:.56rem; text-transform:uppercase; letter-spacing:.055em; }
.dossier-context strong { display:block; color:#fff8f2; font-size:.73rem; margin-top:3px; }
.dossier-footnote { color:#806f68; font-size:.58rem; line-height:1.4; padding:7px 2px 0; }
.grade-summary-strip { display:flex; gap:8px; flex-wrap:wrap; margin:4px 0 12px; }
.grade-summary-pill { border-radius:999px; padding:7px 10px; font-size:.68rem; font-weight:900; border:1px solid var(--line-soft); background:rgba(255,255,255,.02); }
.grade-summary-pill.green { color:#9af0b6; border-color:rgba(74,222,128,.28); background:rgba(74,222,128,.055); }
.grade-summary-pill.gold { color:#ffe08b; border-color:rgba(251,191,36,.33); background:rgba(251,191,36,.065); }
.grade-summary-pill.muted { color:#a9958b; }

@media (max-width: 800px) {
  .matchup-head,.matchup-row { grid-template-columns:minmax(105px,.9fr) repeat(2,minmax(65px,1fr)); }
  .dossier-context-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .intel-dossier > summary span:last-child { display:none; }
}


/* v1.3 Betting Intelligence */
.chip.projection { color:#d8f8f4; border-color:rgba(45,212,191,.23); background:rgba(45,212,191,.045); }
.chip.market { color:#fef3c7; border-color:rgba(251,191,36,.34); background:rgba(251,191,36,.075); }

.betting-snapshot { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin-top:10px; }
.profile-metric { position:relative; background:rgba(255,255,255,.022); border:1px solid rgba(231,203,188,.09); border-radius:10px; padding:9px; min-width:0; }
.profile-metric > span:first-child { display:block; color:var(--muted); font-size:.57rem; text-transform:uppercase; letter-spacing:.06em; font-weight:750; }
.profile-metric strong { display:block; color:#fff8f2; font-size:.84rem; font-weight:950; margin-top:3px; overflow:hidden; text-overflow:ellipsis; }
.profile-note { display:block; color:#806f68 !important; font-size:.50rem !important; text-transform:none !important; letter-spacing:0 !important; margin-top:2px; }

.result-banner { grid-template-columns:42px auto 1fr; grid-template-areas:"mark copy outcomes" "line line line"; padding:10px 11px; }
.result-mark { grid-area:mark; width:34px; height:34px; border-radius:10px; display:flex; align-items:center; justify-content:center; color:#190d05; background:#8f7c75; font-size:1.02rem; font-weight:1000; box-shadow:inset 0 0 0 1px rgba(255,255,255,.18); }
.result-copy { grid-area:copy; min-width:0; }
.result-headline { color:#f6e7de; font-size:.59rem; font-weight:950; letter-spacing:.09em; }
.result-banner.win { border-color:rgba(74,222,128,.44); background:linear-gradient(90deg,rgba(34,197,94,.20),rgba(74,222,128,.055) 62%,rgba(255,255,255,.015)); }
.result-banner.win .result-mark { background:linear-gradient(135deg,#4ade80,#22c55e); color:#06140a; box-shadow:0 0 20px rgba(74,222,128,.14); }
.result-banner.sweep { border-color:rgba(251,191,36,.70); background:linear-gradient(90deg,rgba(251,191,36,.28),rgba(245,158,11,.13) 55%,rgba(249,115,22,.035)); box-shadow:0 0 28px rgba(251,191,36,.10); }
.result-banner.sweep .result-mark { background:linear-gradient(135deg,#fde68a,#fbbf24 50%,#f59e0b); color:#1d1200; box-shadow:0 0 24px rgba(251,191,36,.24); }
.result-banner.sweep .result-headline { color:#ffe7a6; }
.result-banner.loss .result-mark { background:rgba(251,113,133,.12); color:#ffb1bd; border:1px solid rgba(251,113,133,.28); }
.result-final { margin-top:2px; }

.team-profile-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; margin-top:10px; }
.team-profile-card { border:1px solid var(--line-soft); border-radius:14px; padding:12px; background:linear-gradient(145deg,rgba(29,18,22,.95),rgba(18,11,14,.95)); }
.team-profile-card.focus { border-color:rgba(251,191,36,.23); }
.team-profile-card.selected { background:linear-gradient(145deg,rgba(66,36,20,.36),rgba(22,13,16,.96)); }
.team-profile-head { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:9px; }
.team-profile-head div > span { display:block; color:#a9958b; font-size:.53rem; font-weight:900; letter-spacing:.09em; }
.team-profile-head div > strong { display:block; color:#fff7ed; font-size:1rem; margin-top:2px; }
.pick-check { display:flex; width:24px; height:24px; border-radius:50%; align-items:center; justify-content:center; background:rgba(74,222,128,.11); border:1px solid rgba(74,222,128,.28); color:#83efaa; font-weight:950; }
.team-profile-metrics { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:7px; }

.battle-shell { border:1px solid rgba(45,212,191,.14); background:rgba(45,212,191,.025); border-radius:13px; padding:10px 11px; margin-top:10px; }
.battle-title { color:#8feee5; font-size:.57rem; font-weight:950; letter-spacing:.09em; margin-bottom:7px; }
.battle-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:7px; }
.battle-card { border:1px solid rgba(45,212,191,.10); border-radius:9px; padding:8px; background:rgba(255,255,255,.015); }
.battle-card span { display:block; color:#a9958b; font-size:.54rem; text-transform:uppercase; letter-spacing:.055em; }
.battle-card strong { display:block; color:#f8fffe; font-size:.83rem; margin-top:2px; }
.battle-card em { display:block; color:#74645e; font-size:.52rem; font-style:normal; margin-top:2px; line-height:1.35; }

.market-context { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:5px 10px; align-items:center; border-radius:12px; padding:10px 11px; margin-top:10px; border:1px solid rgba(148,163,184,.12); background:rgba(255,255,255,.015); }
.market-context > div:first-child span { display:block; color:#9f8c83; font-size:.54rem; font-weight:900; letter-spacing:.08em; }
.market-context > div:first-child strong { display:block; color:#fff3d4; font-size:.86rem; margin-top:2px; }
.market-context p { grid-column:1/-1; margin:2px 0 0; color:#7f6d66; font-size:.56rem; line-height:1.4; }
.market-context.live { border-color:rgba(251,191,36,.22); background:rgba(251,191,36,.035); }
.market-gap { color:#ffe19a; font-size:.72rem; font-weight:900; text-align:right; }
.market-close { grid-column:1/-1; color:#a9958b; font-size:.58rem; }

.team-dossier-hero { display:grid; grid-template-columns:1fr auto; gap:12px; align-items:center; border:1px solid rgba(251,191,36,.22); background:linear-gradient(90deg,rgba(251,191,36,.075),rgba(249,115,22,.025)); border-radius:15px; padding:14px 15px; margin:6px 0 12px; }
.team-dossier-hero > div:last-child { text-align:right; }
.team-dossier-hero span { display:block; color:#bda99f; font-size:.58rem; font-weight:900; letter-spacing:.08em; }
.team-dossier-hero strong { display:block; color:#fff7ed; font-size:1.25rem; font-weight:950; margin-top:2px; }
.team-dossier-hero p { margin:2px 0 0; color:#8e7b73; font-size:.64rem; }

@media (max-width:950px) {
  .battle-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
}
@media (max-width:700px) {
  .betting-snapshot { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .team-profile-grid { grid-template-columns:1fr; }
  .team-profile-metrics { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .battle-grid { grid-template-columns:1fr 1fr; }
  .result-banner { grid-template-columns:38px 1fr; grid-template-areas:"mark copy" "outcomes outcomes" "line line"; }
  .result-outcomes { justify-content:flex-start; }
  .team-dossier-hero { grid-template-columns:1fr; }
  .team-dossier-hero > div:last-child { text-align:left; }
}


.help-dot { position:relative; display:inline-flex; align-items:center; justify-content:center; width:13px; height:13px; margin-left:5px; border-radius:50%; border:1px solid rgba(231,203,188,.30); color:#ccb9af; font-size:.52rem; font-weight:950; line-height:1; cursor:help; vertical-align:1px; text-transform:none; letter-spacing:0; outline:none; }
.help-dot::after { content:attr(data-tooltip); position:absolute; z-index:10000; left:50%; bottom:calc(100% + 9px); transform:translateX(-50%) translateY(3px); width:max-content; max-width:280px; min-width:210px; padding:9px 11px; border:1px solid rgba(245,158,11,.30); border-radius:9px; background:#171014; color:#fff7ed; box-shadow:0 10px 28px rgba(0,0,0,.38); font-size:.68rem; font-weight:650; line-height:1.42; text-align:left; text-transform:none; letter-spacing:0; white-space:normal; opacity:0; visibility:hidden; pointer-events:none; transition:opacity .12s ease, transform .12s ease, visibility .12s ease; }
.help-dot::before { content:""; position:absolute; z-index:10001; left:50%; bottom:calc(100% + 4px); width:8px; height:8px; background:#171014; border-right:1px solid rgba(245,158,11,.30); border-bottom:1px solid rgba(245,158,11,.30); transform:translateX(-50%) rotate(45deg); opacity:0; visibility:hidden; pointer-events:none; transition:opacity .12s ease, visibility .12s ease; }
.help-dot:hover::after, .help-dot:focus::after, .help-dot:focus-visible::after { opacity:1; visibility:visible; transform:translateX(-50%) translateY(0); }
.help-dot:hover::before, .help-dot:focus::before, .help-dot:focus-visible::before { opacity:1; visibility:visible; }
.metric-shell[title], .profile-metric[title], .dossier-context[title], .battle-card[title] { cursor:help; }
.metric-glossary { margin-top:10px; border:1px solid rgba(231,203,188,.10); border-radius:11px; background:rgba(255,255,255,.015); }
.metric-glossary > summary { cursor:pointer; list-style:none; padding:9px 10px; color:#cdbbb2; font-size:.66rem; font-weight:900; }
.metric-glossary > summary::-webkit-details-marker { display:none; }
.metric-glossary-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:7px; padding:0 10px 10px; }
.metric-glossary-grid > div { border:1px solid rgba(231,203,188,.08); border-radius:9px; padding:8px; background:rgba(255,255,255,.012); }
.metric-glossary-grid strong { display:block; color:#fff6ef; font-size:.65rem; }
.metric-glossary-grid span { display:block; color:#927f77; font-size:.58rem; line-height:1.42; margin-top:2px; }
@media (max-width:700px) { .metric-glossary-grid { grid-template-columns:1fr; } }

</style>
"""
