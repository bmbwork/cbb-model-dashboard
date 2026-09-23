from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st

_SESSION_KEY = "_stat_factory_access"
_LAUNCH_VERIFY_URL = "https://stat-factory.com/api/launch/verify"
_SESSION_VERIFY_URL = "https://stat-factory.com/api/launch/session/verify"
_RECHECK_SECONDS = 60


def _query_token() -> str:
    try:
        value = st.query_params.get("access_token", "")
        if isinstance(value, list):
            value = value[0] if value else ""
        return str(value or "").strip()
    except Exception:
        return ""


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "StatFactory-Streamlit-Gate/3.0",
        },
    )
    try:
        with urlopen(request, timeout=6.0) as response:
            if response.status != 200:
                return None
            result = json.loads(response.read(16384).decode("utf-8"))
            return result if result.get("ok") is True else None
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None


def _exchange_launch_token(token: str, expected_product: str) -> dict[str, Any] | None:
    if not token or len(token) > 4096:
        return None
    result = _post_json(
        _LAUNCH_VERIFY_URL,
        {"token": token, "product": expected_product},
    )
    if not result or result.get("product") != expected_product:
        return None
    return result


def _verify_dashboard_session(token: str, expected_product: str) -> dict[str, Any] | None:
    if not token or len(token) > 4096:
        return None
    result = _post_json(
        _SESSION_VERIFY_URL,
        {"token": token, "product": expected_product},
    )
    if not result or result.get("product") != expected_product:
        return None
    return result


def _save_parent_session(result: dict[str, Any], expected_product: str) -> None:
    token = str(result.get("dashboard_session_token") or "").strip()
    try:
        expires_at = float(result.get("dashboard_session_expires_at") or 0)
    except (TypeError, ValueError):
        expires_at = 0
    st.session_state[_SESSION_KEY] = {
        "product": expected_product,
        "valid_until": expires_at,
        "feed_token": token,
        "feed_expires_at": expires_at,
        "last_verified_at": time.time(),
    }


def _cached_session_valid(expected_product: str) -> bool:
    cached = st.session_state.get(_SESSION_KEY)
    if not isinstance(cached, dict) or cached.get("product") != expected_product:
        return False

    token = str(cached.get("feed_token") or "").strip()
    try:
        valid_until = float(cached.get("valid_until") or 0)
        last_verified = float(cached.get("last_verified_at") or 0)
    except (TypeError, ValueError):
        return False

    now = time.time()
    if not token or valid_until <= now:
        return False
    if now - last_verified < _RECHECK_SECONDS:
        return True

    result = _verify_dashboard_session(token, expected_product)
    if not result:
        return False

    try:
        refreshed_expiry = float(result.get("dashboard_session_expires_at") or valid_until)
    except (TypeError, ValueError):
        refreshed_expiry = valid_until
    cached["valid_until"] = refreshed_expiry
    cached["feed_expires_at"] = refreshed_expiry
    cached["last_verified_at"] = now
    st.session_state[_SESSION_KEY] = cached
    return True


def require_stat_factory_access(expected_product: str, session_hours: int = 4) -> None:
    """Require a valid Stat Factory launch and continuously recheck membership.

    Direct Streamlit URLs fail closed. The parent site issues a one-time launch
    credential only after checking the user's current product entitlement or
    staff authority. Active Streamlit sessions revalidate that access with the
    parent at least once per minute on reruns.
    """
    _ = session_hours  # Kept for backwards-compatible call sites.

    if _cached_session_valid(expected_product):
        return

    st.session_state.pop(_SESSION_KEY, None)

    token = _query_token()
    if token:
        result = _exchange_launch_token(token, expected_product)
        if result:
            _save_parent_session(result, expected_product)
            try:
                del st.query_params["access_token"]
            except Exception:
                pass
            return

    st.error("Stat Factory membership access is required to open this dashboard.")
    st.caption(
        "Open this terminal from your Stat Factory account. Typing the Streamlit URL directly does not bypass access."
    )
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
