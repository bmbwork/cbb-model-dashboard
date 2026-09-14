import pandas as pd
from cbb_dashboard.final_results import final_scores, grade_frozen_board


def board():
    return pd.DataFrame({'Game ID':[1,2],'Home Team':['H1','H2'],'Away Team':['A1','A2'],'Model Pick':['H1','A2'],'Home Win Probability':[.7,.4],'Projected Home Score':[80,70],'Projected Away Score':[70,72],'Projected Total':[150,142],'D1 Evaluation Eligible':[True,True]})

def test_only_completed_non_tied_integer_scores():
    payload=[dict(id=1,status='Final',homePoints=80,awayPoints=75),dict(id=2,status='InProgress',homePoints=90,awayPoints=80),dict(id=3,status='Final',homePoints=80,awayPoints=80),dict(id=4,status='Final',homePoints=None,awayPoints=80)]
    assert final_scores(payload)=={'1':(80,75)}

def test_partial_slate_pending_not_loss():
    out=grade_frozen_board(board(),{'1':(80,75)})
    assert out['Grade Eligible'].tolist()==[True,False]
    assert pd.isna(out.loc[1,'Model Winner Correct'])
    assert pd.isna(out.loc[1,'Final Home Score'])
    assert abs(out.loc[0,'Brier Component']-.09)<1e-10

def test_prior_verified_final_survives_provider_gap():
    previous=grade_frozen_board(board(),{'1':(80,75)})
    out=grade_frozen_board(board(),{},previous)
    assert out.loc[0,'Final Home Score']==80

def test_grading_never_changes_forecast_values():
    raw=board(); old=raw.copy(deep=True)
    out=grade_frozen_board(raw,{'1':(80,75)})
    pd.testing.assert_frame_equal(raw,old)
    pd.testing.assert_frame_equal(out[old.columns],old)
