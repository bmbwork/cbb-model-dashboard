from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

import streamlit as st

_SESSION_KEY = "_stat_factory_access"


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
        try:
            values = st.experimental_get_query_params().get("access_token", [])
            return str(values[0] if values else "").strip()
        except Exception:
            return ""


def _decode_segment(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _verify_token(token: str, expected_product: str, secret: str) -> bool:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = base64.urlsafe_b64encode(
            hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
        ).decode("ascii").rstrip("=")
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return False

        payload = json.loads(_decode_segment(encoded).decode("utf-8"))
        now = int(time.time())
        iat = int(payload.get("iat", 0))
        exp = int(payload.get("exp", 0))
        nonce = str(payload.get("nonce", ""))
        return (
            payload.get("product") == expected_product
            and bool(nonce)
            and iat > 0
            and exp > now
            and iat <= now + 60
            and exp - iat <= 600
        )
    except Exception:
        return False


def require_stat_factory_access(expected_product: str, session_hours: int = 12) -> None:
    if not _truthy(_secret("STAT_FACTORY_GATE_ENABLED", "false")):
        return

    secret = str(_secret("STAT_FACTORY_LAUNCH_SECRET", "") or "").strip()
    if not secret:
        st.error("Stat Factory access is enabled, but the launch secret is not configured.")
        st.stop()

    cached = st.session_state.get(_SESSION_KEY)
    if isinstance(cached, dict):
        if cached.get("product") == expected_product and float(cached.get("valid_until", 0)) > time.time():
            return

    token = _query_token()
    if token and _verify_token(token, expected_product, secret):
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
    try:
        st.link_button("Return to Stat Factory", "https://stat-factory.com/account")
    except Exception:
        st.markdown("[Return to Stat Factory](https://stat-factory.com/account)")
    st.stop()
