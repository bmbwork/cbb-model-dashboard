from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import streamlit as st

from . import board_filters
from .conference_context import CONFERENCE_ALL, CONFERENCE_FILTERS, attach_conference_context, filter_conference_status

_ORIGINAL_MULTISELECT = st.multiselect
_ORIGINAL_FILTER_BOARD: Callable[..., pd.DataFrame] | None = None


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


_multiselect._sf_conference_ui = True


def _filtered_board(board: pd.DataFrame, *args, **kwargs) -> pd.DataFrame:
    original = _ORIGINAL_FILTER_BOARD
    if original is None:
        raise RuntimeError("CBB conference filter runtime was not initialized")
    enriched = attach_conference_context(board)
    out = original(enriched, *args, **kwargs)
    mode = str(st.session_state.get("cbb_filter_conference_status", CONFERENCE_ALL) or CONFERENCE_ALL)
    return filter_conference_status(out, mode)


_filtered_board._sf_conference_filter = True


def install_conference_filter_runtime() -> None:
    """Add conference/non-conference discovery to the existing slate filter UI."""
    global _ORIGINAL_FILTER_BOARD

    current_filter = board_filters.filter_board
    if not getattr(current_filter, "_sf_conference_filter", False):
        _ORIGINAL_FILTER_BOARD = current_filter
        board_filters.filter_board = _filtered_board

    if not getattr(st.multiselect, "_sf_conference_ui", False):
        st.multiselect = _multiselect
