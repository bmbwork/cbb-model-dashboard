from pathlib import Path

from cbb_dashboard.data import normalize_board
from cbb_dashboard.intelligence import game_card_html, dossier_html


def test_priority_board_only_offers_top10_and_all():
    app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert '["Top 10", "All"]' in app
    assert '"Top 25"' not in app
    assert '"Top 50"' not in app


def test_public_cards_drop_wide_simulation_range_and_repeated_outcome_chip(board_df):
    board, _ = normalize_board(board_df)
    html = game_card_html(board.iloc[0])
    assert "Likely result range" not in html
    assert "Either team can realistically win" not in html
    assert "Likely range favors" not in html


def test_dossier_drops_likely_result_range(board_df):
    board, _ = normalize_board(board_df)
    html = dossier_html(board.iloc[0])
    assert "Likely result range" not in html
    assert "Typical margin swing" in html
