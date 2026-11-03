from datetime import date
import pandas as pd
import pytest
from cbb_dashboard.final_results import final_scores, grade_frozen_board
from scripts.market_readiness import has_upcoming_board


def test_invalid_game_ids_and_boolean_scores_are_rejected():
    for gid, home in [('bad', 80),(True,80),(1,True),(1,float('inf')),(1,80.5)]:
        assert final_scores([dict(id=gid,status='Final',homePoints=home,awayPoints=70)])=={}


def test_conflicting_provider_finals_are_not_silently_replaced():
    with pytest.raises(ValueError):
        final_scores([dict(id=1,status='Final',homePoints=80,awayPoints=70),dict(id=1,status='Final',homePoints=81,awayPoints=70)])


def test_existing_final_correction_requires_review():
    raw=pd.DataFrame({'Game ID':[1],'Home Team':['H'],'Away Team':['A']})
    old=grade_frozen_board(raw,{'1':(80,70)})
    with pytest.raises(ValueError):grade_frozen_board(raw,{'1':(81,70)},old)


def test_upcoming_board_arms_market_not_stale_historical_demo():
    today=date(2026,9,13)
    assert not has_upcoming_board([{'slate_date':'2026-03-19','board_rows':16}],today)
    assert has_upcoming_board([{'slate_date':'2026-09-14','board_rows':5}],today)
    assert not has_upcoming_board([{'slate_date':'2026-09-14','board_rows':0}],today)
    assert not has_upcoming_board([{'slate_date':'2026-11-01','board_rows':5}],today)
    assert not has_upcoming_board([],today)

def test_cloud_grading_key_trims_outer_whitespace_only():
    from cbb_dashboard.final_results import fetch_scores

    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return [{"id": 12, "status": "Final", "homePoints": 80, "awayPoints": 70}]

    class Session:
        def get(self, url, *, params, headers, timeout):
            assert url == "https://api.collegebasketballdata.com/games"
            assert headers["Authorization"] == "Bearer cbbd_example_token"
            assert timeout == 30
            return Response()

    assert fetch_scores("2026-11-02", "  cbbd_example_token" + chr(10), session=Session()) == {"12": (80, 70)}


def test_cloud_grading_key_rejects_embedded_controls_before_http():
    from cbb_dashboard.final_results import fetch_scores

    class NoNetwork:
        def get(self, *args, **kwargs):
            raise AssertionError("Invalid key must never reach HTTP")

    with pytest.raises(RuntimeError, match="invalid embedded character"):
        fetch_scores("2026-11-02", "partial" + chr(10) + "secret", session=NoNetwork())
