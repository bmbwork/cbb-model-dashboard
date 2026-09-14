"""Cloud final-score poller for current and archived CBB revisions."""
from __future__ import annotations
import argparse, hashlib, json, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from supabase import create_client
from cbb_dashboard.final_results import fetch_scores, grade_frozen_board
from cbb_dashboard.data import dataframe_records
from cbb_dashboard.performance import slate_grade_metrics


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--apply', action='store_true'); parser.add_argument('--lookback-days',type=int,default=14); args=parser.parse_args()
    if not 1 <= args.lookback_days <= 90: parser.error('lookback-days must be between 1 and 90')
    key=os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_SECRET_KEY')
    if not key: raise RuntimeError('Supabase server credential is missing')
    client=create_client(os.environ['SUPABASE_URL'], key)
    today=datetime.now(ZoneInfo('America/Chicago')).date()
    records=[]; start=0
    while True:
        batch=client.table('cbb_slate_revisions').select('*').gte('slate_date',(today-timedelta(days=args.lookback_days)).isoformat()).lte('slate_date',today.isoformat()).order('slate_date').order('revision').range(start,start+199).execute().data or []
        records.extend(batch)
        if len(batch)<200: break
        start+=200
    score_cache={}; changed=0; final_rows=0
    for item in records:
        record=item['record']; day=str(item['slate_date']); board=pd.DataFrame(record['board_json'])
        starts=pd.to_datetime(board.get('Start Time UTC'),utc=True,errors='coerce')
        if starts is not None and starts.notna().any() and starts.min()>pd.Timestamp.now(tz='UTC'): continue
        if day not in score_cache: score_cache[day]=fetch_scores(day,os.environ.get('CBBD_API_KEY',''))
        graded=grade_frozen_board(board,score_cache[day],pd.DataFrame(record.get('grading_json') or []))
        rows=dataframe_records(graded); count=int(graded['Grade Eligible'].sum()); final_rows+=count
        if count==0: continue
        digest=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if digest==record.get('grading_sha256'): continue
        metrics={k:(None if pd.isna(v) else v.item() if hasattr(v,'item') else v) for k,v in slate_grade_metrics(graded).items()}
        now=datetime.now(timezone.utc).isoformat()
        patch={'grading_json':rows,'grading_sha256':digest,'grading_filename':f'cbb_final_scores_{day}.json','graded_at':now,'graded_by':'system:final-score-poller','metrics_json':metrics,'updated_at':now}
        if args.apply:
            saved=client.table('cbb_slate_revisions').update({'record':{**record,**patch}}).eq('slate_date',day).eq('revision',item['revision']).eq('board_sha256',item['board_sha256']).execute().data or []
            if len(saved)!=1: raise RuntimeError('Archived CBB revision changed during grading')
            client.table('cbb_slates').update(patch).eq('slate_date',day).eq('revision',item['revision']).eq('board_sha256',item['board_sha256']).execute()
            verified=client.table('cbb_slate_revisions').select('record').eq('slate_date',day).eq('revision',item['revision']).eq('board_sha256',item['board_sha256']).execute().data or []
            if len(verified)!=1 or verified[0]['record'].get('grading_sha256')!=digest:
                raise RuntimeError('CBB grading readback did not match')
        changed+=1
    print(json.dumps({'apply':args.apply,'revisions_scanned':len(records),'changed_revisions':changed,'final_rows':final_rows}))

if __name__=='__main__': main()
