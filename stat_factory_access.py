from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st

_SESSION_KEY = "_stat_factory_access"
_VERIFY_URL = "https://stat-factory.com/api/launch/verify"


def _secret(name: str, default: Any = "") -> Any:
    try:
        return st.secrets[name]
    except Exception:
        return default


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _query_token() -> str:
    try:
        value = st.query_params.get("access_token", "")
        if isinstance(value, list):
            value = value[0] if value else ""
        return str(value or "").strip()
    except Exception:
        return ""


def _verify_with_parent(token: str, expected_product: str) -> dict[str, Any] | None:
    if not token or len(token) > 4096:
        return None
    payload = json.dumps({"token": token, "product": expected_product}).encode("utf-8")
    request = Request(
        _VERIFY_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "StatFactory-Streamlit-Gate/2.0"},
    )
    try:
        with urlopen(request, timeout=6.0) as response:
            if response.status != 200:
                return None
            result = json.loads(response.read(16384).decode("utf-8"))
            if result.get("ok") is not True or result.get("product") != expected_product:
                return None
            return result
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None


def _save_parent_session(result: dict[str, Any], expected_product: str, session_hours: int) -> None:
    now = time.time()
    feed_token = str(result.get("dashboard_session_token") or "").strip()
    try:
        feed_exp = float(result.get("dashboard_session_expires_at") or 0)
    except (TypeError, ValueError):
        feed_exp = 0
    st.session_state[_SESSION_KEY] = {
        "product": expected_product,
        "valid_until": now + max(1, session_hours) * 3600,
        "feed_token": feed_token,
        "feed_expires_at": feed_exp,
    }


def require_stat_factory_access(expected_product: str, session_hours: int = 4) -> None:
    cached = st.session_state.get(_SESSION_KEY)
    if isinstance(cached, dict):
        if cached.get("product") == expected_product and float(cached.get("valid_until", 0)) > time.time():
            return

    token = _query_token()
    if token:
        result = _verify_with_parent(token, expected_product)
        if result:
            _save_parent_session(result, expected_product, session_hours)
            try:
                del st.query_params["access_token"]
            except Exception:
                pass
            return

    if not _truthy(_secret("STAT_FACTORY_GATE_ENABLED", "false")):
        return

    st.error("Stat Factory membership access is required to open this dashboard.")
    st.caption("Open this model from your Stat Factory account. Direct dashboard URLs do not bypass membership access.")
    try:
        st.link_button("Return to Stat Factory", "https://stat-factory.com/account")
    except Exception:
        st.markdown("[Return to Stat Factory](https://stat-factory.com/account)")
    st.stop()


def stat_factory_feed_token(expected_product: str) -> str:
    cached = st.session_state.get(_SESSION_KEY)
    if not isinstance(cached, dict) or cached.get("product") != expected_product:
        return ""
    token = str(cached.get("feed_token") or "").strip()
    try:
        expires_at = float(cached.get("feed_expires_at") or 0)
    except (TypeError, ValueError):
        return ""
    if not token or expires_at <= time.time() + 5:
        return ""
    return token
