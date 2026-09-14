import pandas as pd

from cbb_dashboard.board_summary_runtime import _summary_html
from cbb_dashboard.board_record_summary import summary_cards


def frame():
    return pd.DataFrame([
        {"Model Pick":"Duke","Win Probability":.80,"_win_prob":.80,"_grade_eligible":True,"_ml_correct":True,"_spread_correct":True,"_filter_best_ml":-220,"_filter_best_spread":-6.5},
        {"Model Pick":"UNC","Win Probability":.60,"_win_prob":.60,"_grade_eligible":True,"_ml_correct":False,"_spread_correct":False,"_filter_best_ml":120,"_filter_best_spread":4.5},
    ]).astype({"_ml_correct":"boolean","_spread_correct":"boolean"})


def test_summary_html_has_exact_six_cfb_style_cards():
    html=_summary_html(frame())
    assert html.count('cbb-record-summary-card')==6
    assert 'ML record' in html and '>1-1<' in html
    assert 'Spread record' in html and '>1-1<' in html
    assert 'Market coverage' in html and '>2/2<' in html


def test_summary_calculation_does_not_mutate_filtered_board():
    board=frame();before=board.copy(deep=True)
    assert len(summary_cards(board))==6
    pd.testing.assert_frame_equal(board,before)


def test_per_rerun_spread_installer_rebinds_stale_app_level_grid_reference(monkeypatch):
    from cbb_dashboard import intelligence
    from cbb_dashboard.spread_display import install_spread_display
    import cbb_dashboard.board_summary_runtime as runtime

    # Simulate a persistent Streamlit worker whose app imported the old function
    # before the new summary wrapper was installed.
    legacy=lambda frame: '<div>legacy</div>'
    monkeypatch.setattr(intelligence,'game_card_grid_html',legacy)
    monkeypatch.setattr(runtime,'_APPLIED',False)
    monkeypatch.setitem(globals(),'game_card_grid_html',legacy)

    install_spread_display()

    assert globals()['game_card_grid_html'] is intelligence.game_card_grid_html
    html=globals()['game_card_grid_html'](frame())
    assert 'cbb-record-summary-grid' in html
    assert html.count('cbb-record-summary-card')==6
