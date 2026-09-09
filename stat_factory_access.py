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


def _verify_with_parent(token: str, expected_product: str) -> bool:
    if not token or len(token) > 4096:
        return False
    payload = json.dumps({"token": token, "product": expected_product}).encode("utf-8")
    request = Request(
        _VERIFY_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "StatFactory-Streamlit-Gate/1.0"},
    )
    try:
        with urlopen(request, timeout=6.0) as response:
            if response.status != 200:
                return False
            result = json.loads(response.read(4096).decode("utf-8"))
            return result.get("ok") is True and result.get("product") == expected_product
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return False


def require_stat_factory_access(expected_product: str, session_hours: int = 4) -> None:
    if not _truthy(_secret("STAT_FACTORY_GATE_ENABLED", "false")):
        return

    cached = st.session_state.get(_SESSION_KEY)
    if isinstance(cached, dict):
        if cached.get("product") == expected_product and float(cached.get("valid_until", 0)) > time.time():
            return

    token = _query_token()
    if token and _verify_with_parent(token, expected_product):
        st.session_state[_SESSION_KEY] = {
            "product": expected_product,
            "valid_until": time.time() + max(1, session_hours) * 3600,
        }
        try:
            del st.query_params["access_token"]
        except Exception:
            pass
        return

    st.error("Stat Factory membership access is required to open this dashboard.")
    st.caption("Open this model from your Stat Factory account. Direct dashboard URLs do not bypass membership access.")
    try:
        st.link_button("Return to Stat Factory", "https://stat-factory.com/account")
    except Exception:
        st.markdown("[Return to Stat Factory](https://stat-factory.com/account)")
    st.stop()
