from __future__ import annotations

from pathlib import Path

from cbb_dashboard.owlsinsight_provider import OwlsInsightConfig, OwlsInsightSplitsProvider


ROOT = Path(__file__).resolve().parents[1]


def _hist_event(i: int) -> dict:
    return {
        "event_id": f"hist-{i}",
        "home_team": f"Home {i}",
        "away_team": f"Away {i}",
        "splits": [],
    }


def test_historical_public_betting_paginates_full_saturday_slate():
    provider = OwlsInsightSplitsProvider(OwlsInsightConfig(api_key="owlsinsight_test_secret"))
    calls = []

    def fake_get(path, params=None):
        calls.append((path, dict(params or {})))
        offset = int((params or {}).get("offset", 0))
        if offset == 0:
            return {"data": [_hist_event(i) for i in range(100)]}
        if offset == 100:
            return {"data": [_hist_event(i) for i in range(100, 137)]}
        return {"data": []}

    provider._get = fake_get  # type: ignore[method-assign]
    payload = provider.historical_public_betting("2026-02-07")

    assert len(payload["data"]) == 137
    assert payload["meta"]["date"] == "2026-02-07"
    assert payload["meta"]["pages_fetched"] == 2
    assert payload["meta"]["records_fetched"] == 137
    assert [c[1]["offset"] for c in calls] == [0, 100]
    assert all(c[0] == "/api/v1/history/public-betting" for c in calls)
    assert all(c[1]["sport"] == "ncaab" for c in calls)
    assert all(c[1]["startDate"] == "2026-02-07" and c[1]["endDate"] == "2026-02-07" for c in calls)
    assert all(c[1]["limit"] == 100 for c in calls)


def test_historical_timestamp_fallback_is_stable_for_reruns():
    payload = {"meta": {"historical": True, "date": "2026-02-07"}}
    first = OwlsInsightSplitsProvider._snapshot_time(payload, {}, {})
    second = OwlsInsightSplitsProvider._snapshot_time(payload, {}, {})
    assert first == second
    assert first.startswith("2026-02-07T23:59:59")


def test_v146_app_exposes_explicit_historical_backfill_control():
    app = (ROOT / "app.py").read_text()
    assert 'APP_VERSION = "1.4.6"' in app
    assert 'Historical Owls Insight backfill (MVP)' in app
    assert 'Backfill historical Owls betting splits' in app
    assert 'datetime(2026, 2, 7).date()' in app
    assert 'publish_hist_public' in app
    assert '/api/v1/history/public-betting' in app


def test_v146_does_not_require_another_database_migration():
    script = (ROOT / "upgrade_github_v1_4_6.sh").read_text()
    assert "No new Supabase migration" in script
    assert "market_terminal_v1_4_6.sql" not in script
