"""Synthetic contract fixtures only; never a production forecast fallback."""
from copy import deepcopy

import pandas as pd
import pytest

from cbb_dashboard.college_research import (
    assessment, attach_college_research, bottom_line, fair_spread_for_pick,
    notable_results_html, team_record_label,
)
from cbb_dashboard.intelligence import dossier_html, game_card_html
from cbb_dashboard.premium_ui_patch import _matchup_banner


NOW = pd.Timestamp("2026-11-21T15:00:00Z")


def board(**updates):
    row = {"Game ID": "g", "Home Team": "Home State", "Away Team": "Away State",
           "Model Pick": "Home State", "Home D1": True, "Away D1": True,
           "Start Time UTC": "2026-11-21T20:00:00Z", "Target Date": "2026-11-21",
           "Win Probability": .7, "Fair Home Spread": -7, "Fair Spread": -7,
           "Projected Home Score": 80, "Projected Away Score": 73,
           "D1 Evaluation Eligible": True, "Deployment Eligible": True}
    row.update(updates)
    return pd.DataFrame([row])


def coverage(**updates):
    c = {"sport": "cbb", "season": 2027, "complete": True, "source": "QA completed season",
         "covered_teams": ["Home State", "Away State"],
         "complete_from": "2026-07-01T00:00:00Z", "complete_through": NOW.isoformat()}
    c.update(updates)
    return [c]


def game(i=0, **updates):
    time = pd.Timestamp("2026-11-01T20:00:00Z") + pd.Timedelta(days=i)
    g = {"sport": "cbb", "season": 2027, "event_id": str(i), "start_time": time.isoformat(),
         "completed_at": (time + pd.Timedelta(hours=3)).isoformat(),
         "home_team": "Home State", "away_team": "Opponent " + str(i), "home_score": 80,
         "away_score": 70, "away_rank": 10, "home_rank": None, "rankings_verified": True,
         "ranking_source": "AP Top 25", "ranking_as_of": "2026-11-01T00:00:00Z",
         "neutral_site": False, "overtimes": None, "result_source": "QA verified final",
         "result_source_url": "https://example.invalid/games/" + str(i), "fetched_at": NOW.isoformat()}
    g.update(updates)
    return g


def attach(history, raw=None, cov=None, quotes=None):
    return attach_college_research(raw if raw is not None else board(), history,
                                   cov if cov is not None else coverage(), quotes, now=NOW,
                                   published_at="2026-11-20T10:00:00Z").iloc[0]


def quote(kind="spread", **updates):
    q = {"Game ID": "g", "Market Type": kind, "Snapshot Time UTC": NOW.isoformat(),
         "Source Label": "Owls Insight · DraftKings", "Home Price": -110, "Away Price": -110,
         "Home Line": -3, "Away Line": 3}
    q.update(updates)
    return pd.DataFrame([q])


def test_ranked_evidence_season_records_and_five_per_team_are_real_and_immutable():
    history = [game(i, home_score=70 if i == 2 else 80, away_score=80 if i == 2 else 70) for i in range(10)]
    original = deepcopy(history)
    raw = board()
    untouched = raw.copy(deep=True)
    row = attach(history, raw)
    assert row["_college_home"]["record"]["wins"] == 9
    assert team_record_label(row, "Home State") == "Home State (9-1)"
    assert len(row["_college_home"]["notable"]) == 5
    text = assessment(row)
    assert text.startswith("Yes")
    assert "AP #10 Opponent 9" in text and "AP #10 Opponent 6" not in text
    html = notable_results_html(row)
    assert html.count("<tr><td>") == 5
    assert "Notable W/Ls" in html and "ranked in the AP Top 25 at tipoff" in html
    assert "Home State (9-1)" in _matchup_banner(row)
    assert history == original
    pd.testing.assert_frame_equal(raw, untouched)


@pytest.mark.parametrize("patch", [
    {"rankings_verified": False}, {"ranking_as_of": "2026-11-22T00:00:00Z"},
    {"ranking_source": "Coaches Poll"}, {"away_rank": 26}, {"away_rank": None},
])
def test_unverified_current_or_wrong_poll_rank_never_becomes_a_notable_game(patch):
    row = attach([game(**patch)])
    assert row["_college_home"]["notable"] == []
    assert "AP #" not in notable_results_html(row)


def test_venue_score_direction_loss_and_overtime_are_preserved():
    row = attach([game(home_team="Other", away_team="Home State", home_score=88,
                       away_score=83, home_rank=3, away_rank=None, overtimes=2)])
    g = row["_college_home"]["notable"][0]
    assert (g["venue"], g["score"], g["opponent_score"], g["result"]) == ("away", 83, 88, "L")
    html = notable_results_html(row)
    assert "Home State @ AP #3 Other" in html and "83-88 (L) (2OT)" in html
    neutral = attach([game(neutral_site=True)])
    assert "Home State N AP #10" in notable_results_html(neutral)


def test_missing_partial_stale_and_non_d1_coverage_never_invents_a_record():
    for cov in ([], coverage(complete=False), coverage(complete_through="2026-11-19T12:00:00Z"),
                coverage(complete_from="2026-11-15T00:00:00Z")):
        row = attach([game()], cov=cov)
        assert row["_college_home"]["record"] is None
        assert team_record_label(row, "Home State") == "Home State"
    assert attach([])["_college_home"]["record"] is None
    assert attach([game()], board(**{"Home D1": False}))["_college_home"]["record"] is None
    assert attach([game(home_score=None)])["_college_home"]["record"] is None


def test_historical_cutoff_excludes_later_games_and_late_known_results():
    raw = board(**{"Start Time UTC": "2026-11-05T12:00:00Z"})
    row = attach([game(1), game(6)], raw)
    assert row["_college_home"]["record"]["wins"] == 1
    assert len(row["_college_home"]["notable"]) == 1
    late = attach([game(1, completed_at=None)], raw)
    assert late["_college_home"]["record"] is None
    assert late["_college_home"]["notable"] == []
    assert "Pass on a new pregame play" in bottom_line(row, now=NOW)


def test_deduplicated_games_and_early_season_do_not_claim_an_established_good_team():
    row = attach([game(), game()])
    assert row["_college_home"]["record"]["wins"] == 1
    assert assessment(row).startswith("It is too early")


def test_uncovered_team_conflicting_result_and_partial_new_run_do_not_make_a_record():
    assert attach([game()], cov=coverage(covered_teams=[]))["_college_home"]["record"] is None
    row = attach([game(), game(home_score=60)])
    assert row["_college_home"]["record"] is None
    assert row["_college_home"]["notable"] == []
    partial = attach([game(fetched_at="2026-11-21T14:59:00Z")],
                     cov=coverage(complete_through="2026-11-21T14:00:00Z"))
    assert partial["_college_home"]["record"] is None
    assert len(partial["_college_home"]["notable"]) == 1


def test_struggling_and_mixed_assessments_use_full_record_not_just_visible_notables():
    struggling = attach([game(i, home_score=60, away_score=80) for i in range(10)])
    assert assessment(struggling).startswith("No")
    mixed = attach([game(i, home_score=80 if i < 5 else 60) for i in range(10)])
    assert "mixed case at 5-5" in assessment(mixed)


def test_bottom_line_spread_uses_selected_team_sign_and_coherent_valid_prices():
    row = attach([], quotes=quote())
    assert "Spread lean: Home State -3.0 at DraftKings" in bottom_line(row, now=NOW)
    assert "4.0 more points" in bottom_line(row, now=NOW)
    assert "not an estimated cover probability" in bottom_line(row, now=NOW)
    away = attach([], board(**{"Model Pick": "Away State", "Fair Spread": -7,
                                 "Fair Home Spread": -7}), quotes=quote())
    assert fair_spread_for_pick(away) == 7
    assert "fair spread of Away State +7.0" in bottom_line(away, now=NOW)
    assert "Pass at the captured prices" in bottom_line(away, now=NOW)


def test_moneyline_value_uses_break_even_price_and_returns_an_actual_underdog_lean():
    row = attach([], quotes=quote("moneyline", **{"Home Price": 120, "Away Price": -140}))
    text = bottom_line(row, now=NOW)
    assert "Underdog moneyline lean: Home State +120 at DraftKings" in text
    assert "break-even rate" in text


@pytest.mark.parametrize("patch", [
    {"Snapshot Time UTC": "2026-11-21T12:00:00Z"},
    {"Snapshot Time UTC": "2026-11-21T15:00:01Z"},
    {"Away Price": None}, {"Away Line": 5},
    {"Source Label": "Owls Insight · Consensus · Multiple books"},
])
def test_no_play_from_stale_future_incomplete_or_mismatched_pairs(patch):
    row = attach([], quotes=quote(**patch))
    assert "Pass for now" in bottom_line(row, now=NOW)
    assert "Spread lean:" not in bottom_line(row, now=NOW)


def test_unknown_publication_and_ineligible_rows_pass_even_with_apparent_value():
    row = attach([], quotes=quote())
    row["_college_published_at"] = None
    assert "publication timing is not verified" in bottom_line(row, now=NOW)
    row = attach([], board(**{"Deployment Eligible": False}), quotes=quote())
    assert "outside the validated" in bottom_line(row, now=NOW)


def test_new_dossier_replaces_repetitive_sections_and_escapes_upstream_text():
    row = attach([game()])
    html = dossier_html(row)
    assert "Is Home State actually good?" in html and "Bottom Line" in html and "Notable W/Ls" in html
    assert "WHAT COULD GO WRONG" not in html and "WHY Home State IS THE PICK" not in html
    assert "Home State (1-0)" in game_card_html(row)
    row["Model Pick"] = "<script>bad</script>"
    assert "<script>bad</script>" not in dossier_html(row)
