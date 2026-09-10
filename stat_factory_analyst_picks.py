from __future__ import annotations

import hashlib
import json
import time
from html import escape
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st

try:
    from stat_factory_access import stat_factory_feed_token
except ImportError:
    # Rolling Streamlit deploys can briefly load this module against an older
    # access helper. Fall back to the public Featured feed rather than crash.
    def stat_factory_feed_token(expected_product: str) -> str:
        return ""

_FEED_ROOT = "https://stat-factory.com/api/dashboard"

_CARD_CSS = """
<style>
.sf-pick-card{position:relative;overflow:hidden;border:1px solid rgba(148,163,184,.18);border-radius:16px;padding:18px 18px 16px;margin:.35rem 0 1rem;background:linear-gradient(155deg,rgba(20,28,38,.92),rgba(8,13,20,.96));box-shadow:0 14px 34px rgba(0,0,0,.10)}
.sf-pick-card:after{content:"";position:absolute;width:180px;height:180px;right:-95px;top:-105px;border-radius:50%;background:rgba(56,189,248,.06);pointer-events:none}.sf-pick-card>*{position:relative;z-index:1}
.sf-pick-top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:16px}.sf-pick-tags{display:flex;flex-wrap:wrap;gap:6px}.sf-chip,.sf-result{display:inline-flex;align-items:center;border:1px solid rgba(148,163,184,.20);border-radius:999px;padding:5px 8px;font-size:.62rem;font-weight:800;letter-spacing:.06em}.sf-chip{color:#cbd5e1;background:rgba(255,255,255,.025)}
.sf-result-open{color:#bae6fd;border-color:rgba(56,189,248,.28);background:rgba(56,189,248,.07)}.sf-result-win{color:#a7f3d0;border-color:rgba(52,211,153,.30);background:rgba(52,211,153,.07)}.sf-result-loss{color:#fecdd3;border-color:rgba(251,113,133,.30);background:rgba(251,113,133,.07)}.sf-result-neutral{color:#dbe4ee;background:rgba(255,255,255,.025)}
.sf-event{color:#8291a4;font-size:.7rem;text-transform:uppercase;letter-spacing:.07em}.sf-selection{font-size:1.42rem;font-weight:850;letter-spacing:-.035em;margin:.28rem 0 .7rem;color:#f8fafc}.sf-analyst{font-size:.84rem;font-weight:800;color:#f1f5f9}.sf-analyst span{font-weight:500;color:#94a3b8}.sf-record{font-size:.7rem;color:#94a3b8;margin-top:.25rem}.sf-meta{display:flex;flex-wrap:wrap;gap:6px;margin:.8rem 0}.sf-meta span{border:1px solid rgba(148,163,184,.16);border-radius:999px;padding:4px 7px;color:#b8c5d3;font-size:.63rem}.sf-analysis{font-size:.86rem;line-height:1.6;color:#d8e0e8;margin:.9rem 0}.sf-pick-footer{display:flex;justify-content:space-between;gap:10px;border-top:1px solid rgba(148,163,184,.13);padding-top:.75rem;color:#718096;font-size:.62rem}
</style>
"""


def _cache_key(product: str) -> str:
    return f"_stat_factory_analyst_feed_{product}"


def _token_marker(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16] if token else "featured"


def load_stat_factory_analyst_picks(product: str, ttl_seconds: int = 20) -> tuple[dict[str, Any] | None, str]:
    token = stat_factory_feed_token(product)
    marker = _token_marker(token)
    cached = st.session_state.get(_cache_key(product))
    if isinstance(cached, dict) and cached.get("marker") == marker and float(cached.get("expires", 0)) > time.time():
        return cached.get("payload"), ""

    headers = {"Accept": "application/json", "User-Agent": "StatFactory-AnalystFeed/1.1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{_FEED_ROOT}/{product}/analyst-picks", headers=headers, method="GET")
    try:
        with urlopen(request, timeout=6.0) as response:
            if response.status != 200:
                return None, f"Stat Factory analyst feed returned HTTP {response.status}."
            payload = json.loads(response.read(512_000).decode("utf-8"))
    except HTTPError as exc:
        return None, f"Stat Factory analyst feed returned HTTP {exc.code}."
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None, "Stat Factory analyst feed is temporarily unavailable."

    if not isinstance(payload, dict) or payload.get("product") != product:
        return None, "Stat Factory analyst feed returned an invalid response."

    st.session_state[_cache_key(product)] = {
        "marker": marker,
        "expires": time.time() + max(5, int(ttl_seconds)),
        "payload": payload,
    }
    return payload, ""


def _fmt_pick(pick: dict[str, Any]) -> str:
    selection = str(pick.get("selection") or "Pick").strip()
    line = pick.get("line")
    if line is not None:
        try:
            suffix = f"{float(line):+g}"
            if suffix not in selection:
                selection = f"{selection} {suffix}"
        except (TypeError, ValueError):
            pass
    odds = pick.get("american_odds")
    if odds is not None:
        try:
            selection += f" ({int(odds):+d})"
        except (TypeError, ValueError):
            pass
    return selection


def _fmt_record(record: dict[str, Any] | None) -> str:
    if not isinstance(record, dict):
        return "Record building"
    wins = int(record.get("wins") or 0)
    losses = int(record.get("losses") or 0)
    pushes = int(record.get("pushes") or 0)
    units = float(record.get("units") or 0)
    return f"{wins}-{losses}-{pushes} · {units:+.2f}u"


def _published_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.replace("T", " ").replace("Z", " UTC")[:16] + " UTC"


def _result_badge(pick: dict[str, Any]) -> tuple[str, str]:
    result = str(pick.get("result") or "pending").lower()
    units_result = pick.get("units_result")
    unit_text = ""
    if result != "pending" and units_result is not None:
        try:
            value = float(units_result)
            unit_text = f" · {value:+.2f}u"
        except (TypeError, ValueError):
            pass
    if result == "win":
        return f"WIN{unit_text}", "sf-result-win"
    if result == "loss":
        return f"LOSS{unit_text}", "sf-result-loss"
    if result in {"push", "void"}:
        return f"{result.upper()}{unit_text}", "sf-result-neutral"
    return "OPEN", "sf-result-open"


def _render_pick_card(pick: dict[str, Any]) -> None:
    analyst = pick.get("analyst") if isinstance(pick.get("analyst"), dict) else {}
    result_text, result_class = _result_badge(pick)
    analysis = escape(str(pick.get("analysis") or "")).replace("\n", "<br>")
    event = escape(str(pick.get("event_label") or ""))
    pick_text = escape(_fmt_pick(pick))
    name = escape(str(analyst.get("name") or "Stat Factory Analyst"))
    title = escape(str(analyst.get("title") or "Analyst"))
    record = escape(_fmt_record(analyst.get("record")))
    book = escape(str(pick.get("sportsbook") or "Reference line"))
    confidence = escape(str(pick.get("confidence") or "standard").replace("_", " ").upper())
    market = escape(str(pick.get("market_type") or "pick").replace("_", " ").upper())
    units = float(pick.get("units_risked") or 1)
    published = escape(_published_label(pick.get("published_at")))
    featured = '<span class="sf-chip">FEATURED</span>' if pick.get("is_featured") else ""
    analysis_html = f'<div class="sf-analysis">{analysis}</div>' if analysis else ""

    st.markdown(
        f"""
<div class="sf-pick-card">
  <div class="sf-pick-top">
    <div class="sf-pick-tags">{featured}<span class="sf-chip">{market}</span></div>
    <span class="sf-result {result_class}">{escape(result_text)}</span>
  </div>
  <div class="sf-event">{event}</div>
  <div class="sf-selection">{pick_text}</div>
  <div class="sf-analyst">{name} <span>· {title}</span></div>
  <div class="sf-record">Season record: {record}</div>
  <div class="sf-meta"><span>{units:.1f}u risked</span><span>{book}</span><span>{confidence}</span></div>
  {analysis_html}
  <div class="sf-pick-footer"><span>Published {published}</span><span>Stat Factory Analyst Desk</span></div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_stat_factory_analyst_picks(product: str, *, heading: bool = True) -> None:
    st.markdown(_CARD_CSS, unsafe_allow_html=True)
    if heading:
        st.markdown("## Analyst Picks")

    payload, error = load_stat_factory_analyst_picks(product)
    if error:
        st.info(error)
        return
    if not payload:
        st.info("No analyst feed is available yet.")
        return

    access = str(payload.get("access") or "featured")
    if access == "member":
        st.caption("Complete Stat Factory analyst feed · picks are timestamped and graded from the parent Analyst Studio · refreshes automatically")
    else:
        st.caption("Featured Stat Factory analyst picks and recent featured results · open through an entitled Stat Factory account for the complete analyst feed")

    picks = payload.get("picks") if isinstance(payload.get("picks"), list) else []
    open_picks = [pick for pick in picks if isinstance(pick, dict) and str(pick.get("result") or "pending") == "pending"]
    settled = [pick for pick in picks if isinstance(pick, dict) and str(pick.get("result") or "pending") != "pending"]

    if not open_picks and not settled:
        st.info("No analyst picks are currently published for this sport.")
        return

    if open_picks:
        st.markdown("### Current selections")
        columns = st.columns(2, gap="large")
        for index, pick in enumerate(open_picks):
            with columns[index % 2]:
                _render_pick_card(pick)

    if settled:
        st.markdown("### Recent results")
        columns = st.columns(2, gap="large")
        for index, pick in enumerate(settled[:20]):
            with columns[index % 2]:
                _render_pick_card(pick)
