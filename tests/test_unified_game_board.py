from pathlib import Path


def test_public_navigation_uses_shared_stat_factory_names():
    root = Path(__file__).resolve().parents[1]
    app = (root / "app.py").read_text(encoding="utf-8")
    assert 'public_pages = ["Home", "Game Board", "Pro Picks", "Performance Lab"]' in app
    assert 'if page == "Game Board"' in app
    assert 'elif page == "Pro Picks"' in app


def test_public_game_board_is_card_only_and_ranked_games_are_emphasized():
    root = Path(__file__).resolve().parents[1]
    app = (root / "app.py").read_text(encoding="utf-8")
    start = app.index("def render_slates_by_date")
    end = app.index("def matchup_label", start)
    board_section = app[start:end]
    assert 'st.segmented_control("Results view"' not in board_section
    assert "st.dataframe" not in board_section
    assert 'with st.form("cbb_game_filters"' in board_section
    assert 'st.multiselect("Teams"' in board_section
    assert 'st.selectbox("AP ranking"' in board_section
    assert 'st.toggle("Filter best ML price"' in board_section
    assert 'st.slider("Minimum spread disagreement"' in board_section
    assert 'st.form_submit_button("GO"' in board_section
    assert "disabled=not ml_enabled" not in board_section
    assert '.ap-tag{display:inline-flex!important' in app
