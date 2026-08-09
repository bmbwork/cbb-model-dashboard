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
</style>
"""
