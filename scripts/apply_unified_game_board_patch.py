from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

old_route = '''        if page == "Today's Board":
            render_board(board, report)
        elif page == "Slates by Date":
            render_slates_by_date(board, report)'''
new_route = '''        if page == "Game Board":
            render_slates_by_date(board, report)'''
if old_route not in text:
    raise SystemExit("Missing CBB board routing block")
text = text.replace(old_route, new_route)

replacements = [
    ('APP_VERSION = "1.6.0"', 'APP_VERSION = "1.6.1"'),
    ('metric_card("Latest published slate", latest, "Open Today\'s Board")', 'metric_card("Latest published slate", latest, "Open Game Board")'),
    ("**Today's Board** is the fast read of the latest published slate. **Slates by Date** is the main research workbench: choose a date, filter the games by AP ranking, model confidence, sportsbook price, market availability, movement and data quality, then inspect the same polished game cards. **Performance Lab** is for historical model evaluation.", "**Game Board** is the main betting workbench: it opens on the latest published slate, lets you choose any saved date, and combines AP ranking, model confidence, sportsbook price, market availability, movement and data-quality filters with the same premium game cards. **Performance Lab** is for historical model evaluation."),
    ('public_pages = ["Home", "Today\'s Board", "Slates by Date", "Analyst Picks", "Performance Lab"]', 'public_pages = ["Home", "Game Board", "Pro Picks", "Performance Lab"]'),
    ('elif page == "Analyst Picks":', 'elif page == "Pro Picks":'),
    ('CBB MODEL <span style="color:#fbbf24">//</span> ANALYST PICKS', 'CBB MODEL <span style="color:#fbbf24">//</span> PRO PICKS'),
    ('if page == "Slates by Date":', 'if page == "Game Board":'),
    ('<div class="cbb-kicker">SLATES BY DATE</div>', '<div class="cbb-kicker">GAME BOARD</div>'),
    ('<div class="cbb-title">FIND THE <span style="color:#f97316">SLATE</span></div>', '<div class="cbb-title">CBB <span style="color:#f97316">GAME BOARD</span></div>'),
    ('Choose a published date, then narrow the board by team, AP ranking, model confidence, sportsbook price and market behavior.', 'Choose the latest or any published slate, then narrow the board by team, AP ranking, model confidence, sportsbook price and market behavior.'),
    ('render_header(report, record, compact=(page == "Slates by Date"))', 'render_header(report, record, compact=(page == "Game Board"))'),
]
for old, new in replacements:
    if old not in text:
        raise SystemExit(f"Missing expected CBB source fragment: {old[:100]}")
    text = text.replace(old, new)

old_view = '''    view = st.segmented_control("Results view", ["Cards", "Table"], default="Cards", label_visibility="collapsed")
    if view == "Cards":
        limit_choice = st.segmented_control("Cards shown", ["Top 10", "Top 25", "All"], default="Top 25", label_visibility="collapsed")
        limit = {"Top 10": 10, "Top 25": 25, "All": len(filtered)}.get(limit_choice, 25)
        st.markdown(game_card_grid_html(filtered.head(limit)), unsafe_allow_html=True)
        if limit < len(filtered):
            st.caption(f"Showing {limit} of {len(filtered)} matching games. Choose All to render the full filtered slate.")
    else:
        st.dataframe(_compact_slate_table(filtered), use_container_width=True, hide_index=True, height=min(760, 70 + 35 * max(5, len(filtered))))'''
if old_view not in text:
    raise SystemExit("Could not locate CBB public Cards/Table result block")
new_view = '''    limit_choice = st.segmented_control("Cards shown", ["Top 10", "Top 25", "All"], default="Top 25", label_visibility="collapsed")
    limit = {"Top 10": 10, "Top 25": 25, "All": len(filtered)}.get(limit_choice, 25)
    st.markdown(game_card_grid_html(filtered.head(limit)), unsafe_allow_html=True)
    if limit < len(filtered):
        st.caption(f"Showing {limit} of {len(filtered)} matching games. Choose All to render the full filtered slate.")'''
text = text.replace(old_view, new_view)

css_anchor = 'st.markdown(GLOBAL_CSS, unsafe_allow_html=True)\n'
if css_anchor not in text:
    raise SystemExit("Missing GLOBAL_CSS anchor")
rank_css = '''st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
st.markdown(r"""
<style>
.ap-tag{display:inline-flex!important;align-items:center!important;padding:.24rem .48rem!important;margin-right:.38rem!important;border-radius:999px!important;border:1px solid rgba(251,191,36,.68)!important;background:linear-gradient(135deg,rgba(251,191,36,.24),rgba(249,115,22,.08))!important;color:#ffe5a0!important;font-size:.72rem!important;font-weight:950!important;letter-spacing:.045em!important;box-shadow:0 0 16px rgba(251,191,36,.10)!important}
.game-card:has(.ap-tag){border-color:rgba(251,191,36,.25)!important;box-shadow:0 14px 34px rgba(0,0,0,.22),0 0 22px rgba(251,191,36,.035)!important}
.game-card:has(.ap-tag) .game-head.polished{border-top:1px solid rgba(251,191,36,.12)!important}
</style>
""", unsafe_allow_html=True)
'''
text = text.replace(css_anchor, rank_css, 1)
path.write_text(text, encoding="utf-8")
