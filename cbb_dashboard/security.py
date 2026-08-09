from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any


@dataclass(frozen=True)
class AdminAccess:
    authenticated: bool
    authorized: bool
    email: str
    reason: str


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def evaluate_admin_identity(user: dict[str, Any] | None, admin_email: str, now: datetime | None = None) -> AdminAccess:
    data = dict(user or {})
    email = str(data.get("email") or "").strip().lower()
    target = str(admin_email or "").strip().lower()
    if not email:
        return AdminAccess(False, False, "", "not_authenticated")

    if "email_verified" in data and not _truthy(data.get("email_verified")):
        return AdminAccess(True, False, email, "email_not_verified")

    if data.get("exp") is not None:
        try:
            now_ts = int((now or datetime.now(timezone.utc)).timestamp())
            if int(float(data["exp"])) <= now_ts:
                return AdminAccess(True, False, email, "identity_expired")
        except Exception:
            return AdminAccess(True, False, email, "invalid_expiration")

    if not target:
        return AdminAccess(True, False, email, "admin_email_not_configured")
    if email != target:
        return AdminAccess(True, False, email, "not_allowlisted")
    return AdminAccess(True, True, email, "authorized")


def audit_actor(email: str) -> str:
    raw = str(email or "").strip().lower().encode("utf-8")
    return "owner_" + hashlib.sha256(raw).hexdigest()[:16]
