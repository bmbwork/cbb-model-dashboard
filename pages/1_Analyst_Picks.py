from __future__ import annotations

import streamlit as st

from cbb_dashboard.ui import GLOBAL_CSS
from stat_factory_access import require_stat_factory_access
from stat_factory_analyst_picks import render_stat_factory_analyst_picks

require_stat_factory_access("cbb")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

st.markdown('<div class="cbb-kicker">COLLEGE BASKETBALL INTELLIGENCE</div>', unsafe_allow_html=True)
st.markdown('<div class="cbb-title">CBB MODEL <span style="color:#fbbf24">//</span> PRO PICKS</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="cbb-subtitle">Official human selections published from Stat Factory • separate from the independent CBB forecast engine</div>',
    unsafe_allow_html=True,
)

st.info("Pro Picks are an editorial layer. They may reference model output and sportsbook context, but they do not feed back into or alter the frozen CBB model forecast.")
render_stat_factory_analyst_picks("cbb", heading=False)
