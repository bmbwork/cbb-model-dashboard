import pandas as pd
import pytest
from cbb_dashboard.spread_display import graded_spread,result_banner,install_spread_display


def illinois():
    return pd.Series({'Home Team':'UConn','Away Team':'Illinois','Model Pick':'Illinois','Fair Spread':-4.3,
                      '_grade_eligible':True,'_final_away':62,'_final_home':71,'_ml_correct':False,
                      'Projected Away Score':76.7,'Projected Home Score':72.4,'Win Probability':.687})


def test_actual_illinois_final_has_model_line_loss_not_fabricated_ats_result():
    row=illinois();before=row.copy(deep=True)
    result=graded_spread(row)
    assert result['kind']=='model' and result['result']=='L'
    assert result['clearance']==pytest.approx(-13.3)
    html=result_banner(row)
    assert 'MODEL LINE <strong>L</strong>' in html
    assert 'no sportsbook wager was recorded' in html
    assert 'Illinois -4.3' in html
    pd.testing.assert_series_equal(row,before)


def test_saved_away_sportsbook_spread_takes_priority_over_model_line():
    row=illinois();row['Taken Home Spread']=-10
    result=graded_spread(row)
    assert result['kind']=='sportsbook' and result['line']==10 and result['result']=='W'
    assert 'SPREAD <strong>W</strong>' in result_banner(row)
    row['Taken Home Spread']=-9
    assert graded_spread(row)['result']=='PUSH'


def test_saved_home_spread_and_zero_line_are_valid():
    row=illinois();row['Model Pick']='UConn';row['Taken Home Spread']=-9
    assert graded_spread(row)['result']=='PUSH'
    row['Taken Home Spread']=0
    assert graded_spread(row)['result']=='W'


@pytest.mark.parametrize('field,value',[('_grade_eligible',False),('_final_home',None),('_final_home',True),('_final_away',62.5),('_final_home',float('inf'))])
def test_pending_or_invalid_final_never_yields_a_result(field,value):
    row=illinois();row[field]=value
    assert graded_spread(row)['result'] is None
    assert result_banner(row)==''


def test_close_only_market_does_not_get_presented_as_a_taken_wager():
    row=illinois();row['Closing Home Spread']=-10
    assert graded_spread(row)['kind']=='model'


def test_active_game_card_calls_the_new_banner_and_preserves_logos():
    from cbb_dashboard import intelligence
    from cbb_dashboard.premium_ui_patch import apply_premium_ui_patch
    apply_premium_ui_patch();install_spread_display()
    row=illinois()
    html=intelligence.game_card_html(row)
    assert 'MODEL LINE <strong>L</strong>' in html
    assert 'data:image/png;base64,' in html
