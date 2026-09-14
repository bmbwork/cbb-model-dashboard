from pathlib import Path

path = Path("app.py")
source = path.read_text()
old = """from cbb_dashboard.spread_display import install_spread_display
install_spread_display()
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)"""
new = """from cbb_dashboard.spread_display import install_spread_display
from cbb_dashboard.board_summary_runtime import install_board_summary_runtime
from cbb_dashboard import intelligence as _cbb_intelligence
install_spread_display()
install_board_summary_runtime()
# app.py imports the grid before runtime installation; rebind the local symbol on
# every Streamlit rerun so source-sync workers cannot retain the old renderer.
game_card_grid_html = _cbb_intelligence.game_card_grid_html
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)"""
if source.count(old) != 1:
    raise SystemExit("Expected the live spread installer block exactly once")
source = source.replace(old, new, 1)
if source.count('APP_VERSION = "1.6.3"') != 1:
    raise SystemExit("Expected CBB app version 1.6.3 exactly once")
source = source.replace('APP_VERSION = "1.6.3"', 'APP_VERSION = "1.6.4"', 1)
compile(source, "app.py", "exec")
path.write_text(source)
