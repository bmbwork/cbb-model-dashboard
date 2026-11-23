"""Cloud final-score poller for current and archived CBB revisions."""
from __future__ import annotations
import argparse, hashlib, json, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from supabase import create_client
from cbb_dashboard.final_results import fetch_scores, grade_frozen_board, final_scores
from cbb_dashboard.recovery import PipelineRun,AlreadyRunning,safe_error
from cbb_dashboard.data import dataframe_records
from cbb_dashboard.performance import slate_grade_metrics


TERMINAL_NON_GRADED = {"canceled", "cancelled"}


def _bool_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index, dtype=bool)
    values = frame[column]
    if values.dtype == bool:
        return values.fillna(False).astype(bool)
    return values.map(lambda v: str(v).strip().lower() in {"true","1","yes","y"}).fillna(False).astype(bool)


def _grading_is_settled(previous: pd.DataFrame, expected_rows: int) -> bool:
    if previous is None or previous.empty or expected_rows <= 0 or len(previous) != expected_rows:
        return False
    eligible = _bool_series(previous, "Grade Eligible")
    if int(eligible.sum()) == expected_rows:
        return True
    status = previous.get("Status", pd.Series("", index=previous.index)).fillna("").astype(str).str.strip().str.lower()
    return bool((eligible | status.isin(TERMINAL_NON_GRADED)).all())


def _verified_scores_by_day(records):
    """Reuse already verified finals across immutable revisions of one slate."""
    known = {}
    for item in records:
        day = str(item['slate_date'])
        scores = known.setdefault(day,{})
        previous = pd.DataFrame(item['record'].get('grading_json') or [])
        if previous.empty:
            continue
        eligible = previous.loc[_bool_series(previous,'Grade Eligible')]
        for row in eligible.to_dict('records'):
            parsed = final_scores([{'id':row.get('Game ID'),'status':'Final','homePoints':row.get('Final Home Score'),'awayPoints':row.get('Final Away Score')}])
            for game,value in parsed.items():
                if game in scores and scores[game] != value:
                    scores[game] = None  # Conflicting history requires a fresh official result.
                elif game not in scores:
                    scores[game] = value
    return {day:{game:value for game,value in scores.items() if value is not None} for day,scores in known.items()}


def grade_records(client,records,fetcher,*,apply=False):
    # Work newest first. A bad archived revision must not starve today's finals.
    ordered = sorted(records,key=lambda r:(str(r['slate_date']),int(r['revision'])),reverse=True)
    known = _verified_scores_by_day(records)
    cache = {}; failed_dates = {}; changed = 0; final_rows = 0; settled = 0; failures = []
    for item in ordered:
        day = str(item['slate_date'])
        try:
            record=item['record'];board=pd.DataFrame(record.get('board_json') or [])
            if board.empty:
                continue
            starts=pd.to_datetime(board.get('Start Time UTC'),utc=True,errors='coerce')
            if starts is not None and starts.notna().any() and starts.min()>pd.Timestamp.now(tz='UTC'):
                continue
            previous=pd.DataFrame(record.get('grading_json') or [])
            if _grading_is_settled(previous,len(board)):
                settled+=1
                continue
            ids={str(int(float(value))) for value in board['Game ID']}
            scores=known.get(day,{})
            if not ids.issubset(scores):
                if day in failed_dates:
                    raise failed_dates[day]
                if day not in cache:
                    try:
                        cache[day]=fetcher(day)
                    except Exception as exc:
                        failed_dates[day]=exc
                        raise
                # grade_frozen_board checks corrections against this revision.
                scores=cache[day]
            graded=grade_frozen_board(board,scores,previous)
            rows=dataframe_records(graded);count=int(graded['Grade Eligible'].sum());final_rows+=count
            if not count:
                continue
            digest=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if digest==record.get('grading_sha256'):
                continue
            metrics={k:(None if pd.isna(v) else v.item() if hasattr(v,'item') else v) for k,v in slate_grade_metrics(graded).items()}
            now=datetime.now(timezone.utc).isoformat()
            patch={'grading_json':rows,'grading_sha256':digest,'grading_filename':f'cbb_final_scores_{day}.json','graded_at':now,'graded_by':'system:final-score-poller','metrics_json':metrics,'updated_at':now}
            if apply:
                saved=client.table('cbb_slate_revisions').update({'record':{**record,**patch}}).eq('slate_date',day).eq('revision',item['revision']).eq('board_sha256',item['board_sha256']).execute().data or []
                if len(saved)!=1:
                    raise RuntimeError('Archived CBB revision changed during grading')
                client.table('cbb_slates').update(patch).eq('slate_date',day).eq('revision',item['revision']).eq('board_sha256',item['board_sha256']).execute()
                verified=client.table('cbb_slate_revisions').select('record').eq('slate_date',day).eq('revision',item['revision']).eq('board_sha256',item['board_sha256']).execute().data or []
                if len(verified)!=1 or verified[0]['record'].get('grading_sha256')!=digest:
                    raise RuntimeError('CBB grading publication readback did not match')
            changed+=1
        except Exception as exc:
            failures.append({'date':day,'revision':item['revision'],'error':safe_error(exc)})
    return {'apply':apply,'revisions_scanned':len(records),'settled_revisions_skipped':settled,'provider_dates_requested':len(cache)+len(failed_dates),'changed_revisions':changed,'final_rows':final_rows,'failed_revisions':failures}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');parser.add_argument('--lookback-days',type=int,default=14);args=parser.parse_args()
    if not 1<=args.lookback_days<=90:parser.error('lookback-days must be between 1 and 90')
    key=os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_SECRET_KEY')
    if not key:raise RuntimeError('Supabase server credential is missing')
    client=create_client(os.environ['SUPABASE_URL'],key)
    def collect(run=None):
        today=datetime.now(ZoneInfo('America/Chicago')).date();records=[];start=0
        while True:
            batch=client.table('cbb_slate_revisions').select('*').gte('slate_date',(today-timedelta(days=args.lookback_days)).isoformat()).lte('slate_date',today.isoformat()).order('slate_date').order('revision').range(start,start+199).execute().data or []
            records.extend(batch)
            if len(batch)<200:break
            start+=200
        summary=grade_records(client,records,lambda day:fetch_scores(day,os.environ.get('CBBD_API_KEY','')),apply=args.apply)
        if run:
            run.rows=summary['final_rows'];run.details=summary
            run.status='idle' if not records else 'completed'
        print(json.dumps(summary),flush=True)
        if summary['failed_revisions']:
            raise RuntimeError('CBB grading has unresolved revision failures; inspect private execution ledger')
    if args.apply:
        with PipelineRun(client,'grading') as run:collect(run)
    else:collect()

if __name__=='__main__':
    try:main()
    except AlreadyRunning:print(json.dumps({'stage':'grading','status':'already_running'}))
