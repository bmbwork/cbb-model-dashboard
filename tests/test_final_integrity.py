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
