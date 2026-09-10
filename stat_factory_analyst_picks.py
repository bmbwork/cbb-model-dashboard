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
    def stat_factory_feed_token(expected_product: str) -> str:
        return ""

_FEED_ROOT = "https://stat-factory.com/api/dashboard"


def _cache_key(product: str) -> str:
    return f"_stat_factory_analyst_feed_{product}"


def _token_marker(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16] if token else "featured"


def load_stat_factory_analyst_picks(product: str, ttl_seconds: int = 30) -> tuple[dict[str, Any] | None, str]:
    token = stat_factory_feed_token(product)
    marker = _token_marker(token)
    cached = st.session_state.get(_cache_key(product))
    if isinstance(cached, dict):
        if cached.get("marker") == marker and float(cached.get("expires", 0)) > time.time():
            return cached.get("payload"), ""

    headers = {"Accept": "application/json", "User-Agent": "StatFactory-AnalystFeed/1.0"}
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

    st.session_state[_cache_key(product)] = {"marker": marker, "expires": time.time() + max(5, int(ttl_seconds)), "payload": payload}
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


def _render_pick_card(pick: dict[str, Any]) -> None:
    analyst = pick.get("analyst") if isinstance(pick.get("analyst"), dict) else {}
    result = str(pick.get("result") or "pending").upper()
    status = "OPEN" if result == "PENDING" else result
    featured = " · FEATURED" if pick.get("is_featured") else ""
    analysis = escape(str(pick.get("analysis") or "")).replace("\n", "<br>")
    event = escape(str(pick.get("event_label") or ""))
    pick_text = escape(_fmt_pick(pick))
    name = escape(str(analyst.get("name") or "Stat Factory Analyst"))
    title = escape(str(analyst.get("title") or "Analyst"))
    record = escape(_fmt_record(analyst.get("record")))
    book = escape(str(pick.get("sportsbook") or "Reference line"))
    confidence = escape(str(pick.get("confidence") or "standard").replace("_", " ").upper())
    units = float(pick.get("units_risked") or 1)
    published = escape(_published_label(pick.get("published_at")))
    with st.container(border=True):
        st.markdown(
            f"""
<div style="font-size:.68rem;letter-spacing:.08em;font-weight:800;color:#94a3b8">{status}{featured}</div>
<div style="font-size:.78rem;color:#94a3b8;margin-top:.55rem">{event}</div>
<div style="font-size:1.35rem;font-weight:850;margin:.18rem 0 .55rem">{pick_text}</div>
<div style="font-size:.82rem"><strong>{name}</strong> · {title}</div>
<div style="font-size:.72rem;color:#94a3b8;margin-top:.2rem">{record}</div>
<div style="font-size:.72rem;color:#94a3b8;margin-top:.65rem">{units:.1f}u · {book} · {confidence}</div>
<div style="font-size:.88rem;line-height:1.55;margin-top:.85rem">{analysis}</div>
<div style="font-size:.66rem;color:#64748b;margin-top:.8rem">Published {published}</div>
""",
            unsafe_allow_html=True,
        )


def render_stat_factory_analyst_picks(product: str, *, heading: bool = True) -> None:
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
        st.caption("Official Stat Factory analyst selections · complete member feed · published and graded from the parent Analyst Studio")
    else:
        st.caption("Featured public analyst selections. Open this dashboard through an entitled Stat Factory account for the complete analyst feed.")

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

    if access == "member" and settled:
        st.markdown("### Recent results")
        for pick in settled[:20]:
            analyst = pick.get("analyst") if isinstance(pick.get("analyst"), dict) else {}
            units_result = pick.get("units_result")
            result_text = str(pick.get("result") or "").upper()
            unit_text = ""
            if units_result is not None:
                try:
                    unit_text = f" · {float(units_result):+.2f}u"
                except (TypeError, ValueError):
                    pass
            st.markdown(f"**{escape(_fmt_pick(pick))}** — {escape(str(analyst.get('name') or 'Analyst'))} · {result_text}{unit_text}")
