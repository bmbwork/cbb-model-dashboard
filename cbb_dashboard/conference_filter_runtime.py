from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from . import board_filters
from .conference_context import CONFERENCE_ALL, CONFERENCE_FILTERS, attach_conference_context, filter_conference_status

_INSTALLED = False
_ORIGINAL_MULTISELECT = st.multiselect
_ORIGINAL_FILTER_BOARD = board_filters.filter_board


def _multiselect(label: str, options: Any, *args, **kwargs):
    result = _ORIGINAL_MULTISELECT(label, options, *args, **kwargs)
    if label == "Teams" and kwargs.get("key") in {None, "cbb_filter_teams"}:
        st.selectbox(
            "Conference status",
            CONFERENCE_FILTERS,
            index=0,
            key="cbb_filter_conference_status",
            help="Conference games require both teams to resolve to the same current conference. Non-conference games require two resolved teams in different conferences. This metadata is display-only and never enters V1.1.3B.",
        )
    return result


def _filtered_board(board: pd.DataFrame, *args, **kwargs) -> pd.DataFrame:
    enriched = attach_conference_context(board)
    out = _ORIGINAL_FILTER_BOARD(enriched, *args, **kwargs)
    mode = str(st.session_state.get("cbb_filter_conference_status", CONFERENCE_ALL) or CONFERENCE_ALL)
    return filter_conference_status(out, mode)


def install_conference_filter_runtime() -> None:
    """Add conference/non-conference discovery to the existing slate filter UI."""
    global _INSTALLED
    if _INSTALLED:
        return
    st.multiselect = _multiselect
    _filtered_board._sf_conference_filter = True
    board_filters.filter_board = _filtered_board
    _INSTALLED = True
