from __future__ import annotations

from datetime import datetime, timezone

from cbb_dashboard.security import audit_actor, evaluate_admin_identity


def test_anonymous_denied():
    access = evaluate_admin_identity({}, "owner@example.com")
    assert not access.authenticated
    assert not access.authorized


def test_exact_allowlist_only():
    good = evaluate_admin_identity({"email": "owner@example.com", "email_verified": True}, "OWNER@example.com")
    bad = evaluate_admin_identity({"email": "other@example.com", "email_verified": True}, "owner@example.com")
    assert good.authorized
    assert not bad.authorized


def test_unverified_and_expired_denied():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    unverified = evaluate_admin_identity({"email": "owner@example.com", "email_verified": False}, "owner@example.com", now=now)
    expired = evaluate_admin_identity({"email": "owner@example.com", "email_verified": True, "exp": now.timestamp() - 1}, "owner@example.com", now=now)
    assert not unverified.authorized
    assert not expired.authorized


def test_audit_actor_is_not_email():
    actor = audit_actor("owner@example.com")
    assert "owner@example.com" not in actor
    assert actor.startswith("owner_")
