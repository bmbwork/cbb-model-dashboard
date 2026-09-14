from datetime import datetime, timezone
import pandas as pd
import pytest
from stat_factory_board_order import SORT_TIME,SORT_TOSSUPS,SORT_FAVORITES,next_slate_date,sort_cards


def frame():
    return pd.DataFrame({'id':['late','early','unknown','coin'], 'time':['2026-11-02T23:00:00Z','2026-11-02T18:00:00Z',None,'2026-11-02T19:00:00Z'], 'p':[.9,.65,None,.501]})

def test_time_sort_and_missing_last():
    assert sort_cards(frame(),SORT_TIME,time_column='time')['id'].tolist()==['early','coin','late','unknown']

def test_tossup_sort():
    assert sort_cards(frame(),SORT_TOSSUPS,time_column='time',probability_column='p')['id'].tolist()==['coin','early','late','unknown']

def test_favorite_sort():
    assert sort_cards(frame(),SORT_FAVORITES,time_column='time',probability_column='p')['id'].tolist()==['late','early','coin','unknown']

def test_away_favorite_equal_strength():
    f=frame();f.loc[0,'p']=.1
    assert sort_cards(f,SORT_FAVORITES,time_column='time',probability_column='p').iloc[0]['id']=='late'

def test_sort_never_changes_forecast():
    f=frame(); original=f.copy(deep=True)
    sort_cards(f,SORT_TOSSUPS,time_column='time',probability_column='p')
    pd.testing.assert_frame_equal(f,original)

def test_chicago_date_not_utc_date():
    now=datetime(2026,9,14,1,tzinfo=timezone.utc)
    assert next_slate_date(['2026-09-12','2026-09-13','2026-09-17'],now=now)=='2026-09-13'

def test_archive_fallback_and_empty():
    now=datetime(2026,9,14,12,tzinfo=timezone.utc)
    assert next_slate_date(['2026-09-12','2026-09-13'],now=now)=='2026-09-13'
    assert next_slate_date([],now=now) is None

def test_naive_clock_rejected():
    with pytest.raises(ValueError): next_slate_date([],now=datetime(2026,9,14))
