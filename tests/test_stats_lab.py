from pathlib import Path

import pandas as pd

from cbb_dashboard.stats_lab import _flatten_payload, _friendly_frame


ROOT = Path(__file__).resolve().parents[1]


def test_team_stats_lab_preserves_nested_team_and_opponent_fields():
    rows = [
        {
            "payload": {
                "season": 2025,
                "teamId": 1,
                "team": "Example",
                "conference": "B1G",
                "games": 30,
                "wins": 24,
                "losses": 6,
                "pace": 69.2,
                "teamStats": {
                    "points": {"total": 2400},
                    "fourFactors": {
                        "effectiveFieldGoalPct": 0.56,
                        "turnoverRatio": 0.14,
                        "offensiveReboundPct": 0.35,
                    },
                },
                "opponentStats": {
                    "points": {"total": 2050},
                    "fourFactors": {"effectiveFieldGoalPct": 0.48},
                },
            },
            "refreshed_at": "2026-09-29T01:00:00+00:00",
        }
    ]
    frame = _friendly_frame(_flatten_payload(rows))
    assert "Team" in frame.columns
    assert "Wins" in frame.columns
    assert "Team Stats · Points · Total" in frame.columns
    assert "Team Stats · Four Factors · eFG%" in frame.columns
    assert "Opponent Stats · Points · Total" in frame.columns
    assert frame.loc[0, "Team"] == "Example"


def test_player_stats_lab_preserves_advanced_player_fields():
    rows = [
        {
            "payload": {
                "season": 2025,
                "teamId": 1,
                "team": "Example",
                "conference": "B1G",
                "athleteId": 9,
                "name": "Player One",
                "position": "G",
                "games": 31,
                "points": 550,
                "usage": 0.27,
                "offensiveRating": 121.4,
                "defensiveRating": 96.8,
                "netRating": 24.6,
                "PORPAG": 4.9,
                "effectiveFieldGoalPct": 0.58,
                "trueShootingPct": 0.62,
                "rebounds": {"total": 145},
                "winShares": {"total": 5.3},
            },
            "refreshed_at": "2026-09-29T01:00:00+00:00",
        }
    ]
    frame = _friendly_frame(_flatten_payload(rows))
    for column in [
        "Player",
        "Usage",
        "Offensive Rating",
        "Defensive Rating",
        "Net Rating",
        "PORPAG",
        "eFG%",
        "True Shooting %",
        "Rebounds · Total",
        "Win Shares · Total",
    ]:
        assert column in frame.columns


def test_stats_cache_remains_server_only():
    migration = (ROOT / "supabase" / "stats_lab_v1.sql").read_text()
    for table in [
        "cbb_stats_team_season",
        "cbb_stats_player_season",
        "cbb_stats_team_shooting",
        "cbb_stats_player_shooting",
    ]:
        assert f"alter table public.{table} enable row level security" in migration
        assert f"revoke all on table public.{table} from anon, authenticated" in migration


def test_refresh_worker_uses_team_and_player_stats_endpoints():
    worker = (ROOT / "scripts" / "refresh_cbb_stats_lab.py").read_text()
    assert '"/stats/team/season"' in worker
    assert '"/stats/player/season"' in worker
    assert '"/stats/team/shooting/season"' in worker
    assert '"/stats/player/shooting/season"' in worker
    assert "CBBD_API_KEY" in worker
    assert "SUPABASE_SERVICE_ROLE_KEY" in worker


def test_stats_lab_defaults_to_division_one_but_can_expand():
    source = (ROOT / "cbb_dashboard" / "stats_lab.py").read_text()
    assert '"Division I only"' in source
    assert "value=True" in source
    assert 'conference_values.ne("")' in source
