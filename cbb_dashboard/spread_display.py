"""Graded-card spread decisions with explicit provenance.

A saved sportsbook selection is graded as SPREAD. With no such quote, the frozen
fair line can still be evaluated, but is labeled MODEL LINE, never an ATS wager.
"""
from __future__ import annotations

from html import escape
import inspect
import math
from typing import Any

import numpy as np

SAVED_HOME_LINES = ('Bet Home Spread', 'Taken Home Spread', 'Decision Home Spread', 'Market Home Spread', 'Sportsbook Home Spread')


def number(value: Any) -> float | None:
    if isinstance(value, (bool, np.bool_)): return None
    try: value=float(value)
    except (TypeError,ValueError): return None
    return value if math.isfinite(value) else None


def truth(value: Any) -> bool:
    return isinstance(value,(bool,np.bool_)) and bool(value)


def spread_decision(row) -> dict:
    pick=str(row.get('Spread Pick Team') or row.get('Model Pick') or '')
    home,away=str(row.get('Home Team') or ''),str(row.get('Away Team') or '')
    if pick not in (home,away) or not pick:
        return {'kind':'unavailable','team':pick,'line':None,'source':''}
    for field in SAVED_HOME_LINES:
        line=number(row.get(field))
        if line is not None:
            return {'kind':'sportsbook','team':pick,'line':line if pick==home else -line,'source':field}
    source=str(row.get('_spread_source') or '')
    line=number(row.get('_market_home_spread'))
    if source in SAVED_HOME_LINES and line is not None:
        return {'kind':'sportsbook','team':pick,'line':line if pick==home else -line,'source':source}
    # This remains a model diagnostic and cannot inflate the ATS performance record.
    pick=str(row.get('Model Pick') or '')
    fair=number(row.get('Fair Spread'))
    return {'kind':'model' if fair is not None and pick in (home,away) else 'unavailable',
            'team':pick,'line':fair,'source':'Frozen model fair spread'}


def graded_spread(row) -> dict:
    decision=spread_decision(row)
    result={**decision,'result':None,'clearance':None}
    eligible=truth(row.get('_grade_eligible')) or truth(row.get('Grade Eligible'))
    home=number(row.get('_final_home',row.get('Final Home Score')))
    away=number(row.get('_final_away',row.get('Final Away Score')))
    if not eligible or home is None or away is None or home<0 or away<0 or not home.is_integer() or not away.is_integer(): return result
    if decision['line'] is None or decision['kind']=='unavailable': return result
    margin=home-away if decision['team']==str(row.get('Home Team')) else away-home
    clearance=margin+decision['line']
    result.update(clearance=clearance,result='PUSH' if abs(clearance)<1e-9 else 'W' if clearance>0 else 'L')
    return result


def result_banner(row) -> str:
    eligible=truth(row.get('_grade_eligible')) or truth(row.get('Grade Eligible'))
    h=number(row.get('_final_home',row.get('Final Home Score')))
    a=number(row.get('_final_away',row.get('Final Away Score')))
    if not eligible or h is None or a is None or min(h,a)<0 or not h.is_integer() or not a.is_integer(): return ''
    pick=str(row.get('Model Pick') or '')
    winner=str(row.get('Home Team')) if h>a else str(row.get('Away Team'))
    ml='PUSH' if h==a else 'W' if winner==pick else 'L'
    spread=graded_spread(row);label='SPREAD' if spread['kind']=='sportsbook' else 'MODEL LINE'
    def pill(label,result):
        tone='spread-win' if result=='W' else 'loss-pill' if result=='L' else 'pending-pill'
        return f'<span class="result-pill {tone}">{label} <strong>{result or "Unavailable"}</strong></span>'
    if spread['line'] is None:
        detail='Spread decision unavailable: no saved sportsbook or model line.'
    else:
        detail=f"{spread['team']} {spread['line']:+.1f}"
        if spread['result']=='PUSH': detail+=' | landed on the line'
        elif spread['clearance'] is not None:
            detail+=f" | {'covered' if spread['clearance']>0 else 'missed'} by {abs(spread['clearance']):.1f} points"
        detail+=' | Saved pregame sportsbook spread' if spread['kind']=='sportsbook' else ' | Frozen model-line evaluation; no sportsbook wager was recorded'
    wins=int(ml=='W')+int(spread['result']=='W')
    state='sweep' if wins==2 else 'win' if wins else 'loss'
    title='ML + SPREAD SWEEP' if wins==2 and spread['kind']=='sportsbook' else 'WINNING RESULT' if wins else 'FINAL RESULT'
    return (f'<div class="result-banner {state}"><div class="result-mark">{"W" if wins else "P" if ml=="PUSH" else "L"}</div>'
            f'<div class="result-copy"><div class="result-headline">{title}</div><div class="result-final">FINAL {a:.0f}-{h:.0f}</div></div>'
            f'<div class="result-outcomes">{pill("ML",ml)}{pill(label,spread["result"])}</div>'
            f'<div class="result-line">{escape(detail)}</div></div>')


def install_spread_display() -> None:
    """Install current card renderers on every Streamlit rerun.

    The public app imports ``game_card_grid_html`` before calling this installer.
    Streamlit can retain imported modules across a source sync, so updating the
    module function alone can leave that app-level reference stale.  The already
    established spread installer is called on every rerun; use that stable hook to
    install the summary wrapper and rebind the caller's imported grid reference.
    """
    from . import intelligence
    from .board_summary_runtime import install_board_summary_runtime

    intelligence._result_banner=result_banner
    install_board_summary_runtime()

    frame = inspect.currentframe()
    caller = frame.f_back if frame is not None else None
    if caller is not None and 'game_card_grid_html' in caller.f_globals:
        caller.f_globals['game_card_grid_html'] = intelligence.game_card_grid_html
