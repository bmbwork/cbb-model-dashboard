"""Presentation-only wrapper that adds CFB-style summary cards to filtered CBB boards."""
from __future__ import annotations

from html import escape

import pandas as pd

from .board_record_summary import summary_cards

_APPLIED = False

SUMMARY_CSS = r"""
<style>
.cbb-record-summary-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:.65rem;margin:.72rem 0 1rem}
.cbb-record-summary-card{border:1px solid rgba(148,163,184,.13);border-radius:14px;background:linear-gradient(145deg,rgba(30,14,17,.92),rgba(16,9,11,.96));padding:.82rem .86rem;min-width:0}
.cbb-record-summary-label{color:#a89087;font-size:.58rem;font-weight:900;letter-spacing:.085em;text-transform:uppercase}
.cbb-record-summary-value{color:#fff7f1;font-size:1.28rem;font-weight:950;line-height:1.08;margin-top:.44rem;overflow-wrap:anywhere}
.cbb-record-summary-sub{color:#8f7b73;font-size:.61rem;line-height:1.35;margin-top:.34rem}
@media(max-width:1100px){.cbb-record-summary-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:700px){.cbb-record-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _summary_html(frame: pd.DataFrame) -> str:
    cards = summary_cards(frame)
    if not cards:
        return ""
    body = "".join(
        f'<div class="cbb-record-summary-card"><div class="cbb-record-summary-label">{escape(label)}</div>'
        f'<div class="cbb-record-summary-value">{escape(value)}</div>'
        f'<div class="cbb-record-summary-sub">{escape(sub)}</div></div>'
        for label, value, sub in cards
    )
    return f'<div class="cbb-record-summary-grid">{body}</div>'


def install_board_summary_runtime() -> None:
    """Wrap only the filtered Game Board grid; other page grids stay unchanged."""
    global _APPLIED
    if _APPLIED:
        return
    from . import intelligence, ui

    original = intelligence.game_card_grid_html
    if getattr(original, "_sf_record_summary", False):
        _APPLIED = True
        return

    def patched(frame: pd.DataFrame, *args, **kwargs) -> str:
        base = original(frame, *args, **kwargs)
        if frame is None or frame.empty:
            return base
        # render_slates_by_date passes filter_board output, which owns these fields.
        # This avoids duplicating the row on Home/other grids.
        if "_filter_best_ml" not in frame.columns and "_filter_best_spread" not in frame.columns:
            return base
        return _summary_html(frame) + base

    patched._sf_record_summary = True
    intelligence.game_card_grid_html = patched
    if SUMMARY_CSS not in ui.GLOBAL_CSS:
        ui.GLOBAL_CSS += SUMMARY_CSS
    _APPLIED = True
