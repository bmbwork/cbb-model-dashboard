import pandas as pd

from cbb_dashboard.board_record_summary import summary_cards


def board():
    return pd.DataFrame([
        {"Model Pick":"Illinois","Win Probability":.687,"_win_prob":.687,"_grade_eligible":True,"_ml_correct":False,"_spread_correct":False,"_filter_best_ml":-180,"_filter_best_spread":-4.5},
        {"Model Pick":"Oklahoma","Win Probability":.554,"_win_prob":.554,"_grade_eligible":True,"_ml_correct":True,"_spread_correct":pd.NA,"_filter_best_ml":-125,"_filter_best_spread":pd.NA},
        {"Model Pick":"Duke","Win Probability":.810,"_win_prob":.810,"_grade_eligible":False,"_ml_correct":pd.NA,"_spread_correct":pd.NA,"_filter_best_ml":pd.NA,"_filter_best_spread":pd.NA},
    ]).astype({"_ml_correct":"boolean","_spread_correct":"boolean"})


def test_cfb_style_cbb_summary_is_six_cards_and_final_only():
    values={label:(value,sub) for label,value,sub in summary_cards(board())}
    assert len(values)==6
    assert values["Games"][0]=="3"
    assert values["Strongest pick"]==("Duke","81.0% win chance")
    assert values["Average model win"][0]=="68%"
    assert values["ML record"]==("1-1","2 graded finals")
    assert values["Spread record"][0]=="0-1"
    assert values["Market coverage"][0]=="2/3"


def test_missing_spread_and_pending_games_never_become_losses():
    b=board();b["_spread_correct"]=pd.Series([pd.NA,pd.NA,pd.NA],dtype="boolean")
    values={label:(value,sub) for label,value,sub in summary_cards(b)}
    assert values["Spread record"][0]=="—"
    assert "no saved sportsbook spread grades" in values["Spread record"][1]


def test_card_level_model_line_result_cannot_inflate_ats_record():
    b=board();b["_spread_correct"]=pd.Series([pd.NA,pd.NA,pd.NA],dtype="boolean")
    b["Fair Spread"]=[-4.3,-.9,-10.5]
    b["_final_home"]=[71,70,pd.NA]
    b["_final_away"]=[62,80,pd.NA]
    values={label:value for label,value,_ in summary_cards(b)}
    assert values["Spread record"]=="—"
