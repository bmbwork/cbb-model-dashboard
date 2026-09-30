import pandas as pd

from scripts.grade_published import _grading_is_settled


def test_settled_revision_skips_provider_poll_when_all_games_final():
    previous = pd.DataFrame([
        {"Game ID": 1, "Status": "Final", "Grade Eligible": True, "Final Home Score": 80, "Final Away Score": 70},
        {"Game ID": 2, "Status": "Final", "Grade Eligible": True, "Final Home Score": 75, "Final Away Score": 72},
    ])
    assert _grading_is_settled(previous, 2) is True


def test_partial_revision_still_needs_provider_poll():
    previous = pd.DataFrame([
        {"Game ID": 1, "Status": "Final", "Grade Eligible": True},
        {"Game ID": 2, "Status": "Halftime", "Grade Eligible": False},
    ])
    assert _grading_is_settled(previous, 2) is False


def test_terminal_cancel_counts_as_settled_without_fake_grade():
    previous = pd.DataFrame([
        {"Game ID": 1, "Status": "Final", "Grade Eligible": True},
        {"Game ID": 2, "Status": "Cancelled", "Grade Eligible": False},
    ])
    assert _grading_is_settled(previous, 2) is True


def test_mismatched_revision_length_never_skips_provider():
    previous = pd.DataFrame([{"Game ID": 1, "Status": "Final", "Grade Eligible": True}])
    assert _grading_is_settled(previous, 2) is False
