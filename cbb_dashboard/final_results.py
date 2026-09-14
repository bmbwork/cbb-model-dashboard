"""Final-only CBBD grading. Never runs, fits, or modifies a forecasting model."""
from __future__ import annotations
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import requests


def final_scores(payload):
    if not isinstance(payload, list):
        raise ValueError('CBBD games response must be a list')
    result = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        gid = item.get('id', item.get('game_id', item.get('gameId')))
        if gid is None:
            continue
        status = str(item.get('status', '')).strip().lower()
        home = pd.to_numeric(item.get('homePoints', item.get('home_points')), errors='coerce')
        away = pd.to_numeric(item.get('awayPoints', item.get('away_points')), errors='coerce')
        if status != 'final' or pd.isna(home) or pd.isna(away) or min(home, away) < 0 or home == away:
            continue
        if float(home).is_integer() and float(away).is_integer():
            result[str(int(gid))] = (int(home), int(away))
    return result


def fetch_scores(day: str, key: str, session=requests):
    if not key:
        raise RuntimeError('CBBD_API_KEY is required for final scores')
    d = date.fromisoformat(day)
    tz = ZoneInfo('America/Chicago')
    start = datetime.combine(d, time.min, tzinfo=tz)
    end = datetime.combine(d + timedelta(days=1), time.min, tzinfo=tz)
    response = session.get('https://api.collegebasketballdata.com/games', params={
        'startDateRange': start.isoformat(), 'endDateRange': end.isoformat(),
        'season': d.year + (d.month >= 9),
    }, headers={'Authorization': f'Bearer {key}'}, timeout=30)
    response.raise_for_status()
    return final_scores(response.json())


def grade_frozen_board(board, scores, previous=None):
    out = board.copy()
    # Preserve previously verified finals if an upstream response is temporarily incomplete.
    resolved = dict(scores)
    if previous is not None and not previous.empty:
        for row in previous.to_dict('records'):
            if row.get('Grade Eligible') is True:
                h, a = pd.to_numeric(row.get('Final Home Score'), errors='coerce'), pd.to_numeric(row.get('Final Away Score'), errors='coerce')
                if pd.notna(h) and pd.notna(a):
                    resolved.setdefault(str(int(float(row['Game ID']))), (int(h), int(a)))
    ids = out['Game ID'].map(lambda x: str(int(float(x))))
    h = pd.Series([resolved.get(x, (np.nan, np.nan))[0] for x in ids], index=out.index, dtype=float)
    a = pd.Series([resolved.get(x, (np.nan, np.nan))[1] for x in ids], index=out.index, dtype=float)
    mask = h.notna() & a.notna()
    out['Status'] = np.where(mask, 'Final', 'Pending')
    out['Grade Eligible'] = mask
    out['Final Home Score'], out['Final Away Score'] = h, a
    winner = pd.Series(np.where(h > a, out['Home Team'], out['Away Team']), index=out.index).where(mask)
    out['Actual Winner'] = winner
    out['Actual Home Margin'], out['Actual Total'] = h - a, h + a
    out['Home Win Actual'] = (h > a).astype(float).where(mask)
    for prefix, pick, hp, ph, pa, total in [
        ('', 'Model Pick', 'Home Win Probability', 'Projected Home Score', 'Projected Away Score', 'Projected Total'),
        ('V1.0.1 Baseline ', 'V1.0.1 Baseline Pick', 'V1.0.1 Baseline Home Win Probability', 'V1.0.1 Baseline Projected Home Score', 'V1.0.1 Baseline Projected Away Score', 'V1.0.1 Baseline Projected Total'),
    ]:
        if not {pick, hp, ph, pa}.issubset(out.columns):
            continue
        p = pd.to_numeric(out[hp], errors='coerce')
        error = pd.to_numeric(out[ph], errors='coerce') - pd.to_numeric(out[pa], errors='coerce') - (h - a)
        out[prefix + ('Model Winner Correct' if not prefix else 'Winner Correct')] = out[pick].eq(winner).where(mask)
        out[prefix + 'Margin Error'] = error.where(mask)
        out[prefix + 'Absolute Margin Error'] = error.abs().where(mask)
        out[prefix + 'Brier Component'] = ((p - out['Home Win Actual']) ** 2).where(mask)
        clipped = p.clip(1e-6, 1-1e-6)
        out[prefix + 'Log Loss Component'] = (-(out['Home Win Actual'] * np.log(clipped) + (1-out['Home Win Actual']) * np.log(1-clipped))).where(mask)
        if total in out:
            err = pd.to_numeric(out[total], errors='coerce') - (h+a)
            out[prefix+'Total Error'], out[prefix+'Absolute Total Error'] = err.where(mask), err.abs().where(mask)
    if 'D1 Evaluation Eligible' in out:
        d1 = out['D1 Evaluation Eligible'].map(lambda x: str(x).lower() in {'true','1','1.0'})
        out['Primary Evaluation Eligible'] = mask & d1
    return out
