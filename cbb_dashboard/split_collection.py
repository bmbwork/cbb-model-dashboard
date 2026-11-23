"""Background collection of reported Owl splits; forecasts are never written."""
from __future__ import annotations
import re
from datetime import datetime, timezone
from uuid import uuid4
import pandas as pd
from .market import market_records
from .public_consensus import _active_board
from .owlsinsight_provider import annotate_sharp_money_signals
from .recovery import verified_upsert

RUNS = 'cbb_split_refresh_runs'


def _safe_error(exc):
    code = re.search(r'\b(401|403|404|429|500|502|503|504)\b', str(exc))
    return type(exc).__name__ + (' HTTP ' + code[1] if code else '')


def collect_owls_splits(client, provider, *, now=None, dry_run=False):
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    run_id = str(uuid4())
    if not dry_run:
        client.table(RUNS).insert({'id':run_id,'requested_at':current.isoformat(),'status':'running'}).execute()
    try:
        board = _active_board(client,current)
        if not board.empty:
            board["Game ID"]=board["Game ID"].astype(str)
            board["Target Date"]=board["slate_date"].astype(str)
        summary = dict(requested_games=len(board),provider_events=0,mapped_games=0,split_games=0,rows_written=0,feed_state='idle')
        observed = None
        if not board.empty:
            # One call covers every published slate the live provider reports.
            payload = provider.live_splits()
            frame, health = provider.parse(payload,board)
            summary.update({k:int(health[k]) for k in ('provider_events','mapped_games','split_games')})
            summary['feed_state'] = 'not_reported'
            if not frame.empty:
                starts = pd.to_datetime(board.set_index('Game ID')['Start Time UTC'],utc=True,errors='coerce')
                stamp = pd.to_datetime(frame['Snapshot Time UTC'],utc=True,errors='coerce')
                tip = frame['Game ID'].astype(str).map(starts)
                frame = frame[stamp.notna() & tip.notna() & (stamp < tip) & (stamp <= pd.Timestamp(current)+pd.Timedelta(minutes=5))].copy()
                # Reject empty/invalid paired data, including the 0/0 sentinel.
                pairs = [('Home Money %','Away Money %'),('Home Ticket %','Away Ticket %'),('Over Money %','Under Money %'),('Over Ticket %','Under Ticket %')]
                usable = pd.Series(False,index=frame.index)
                for left,right in pairs:
                    a,b = pd.to_numeric(frame[left],errors='coerce'),pd.to_numeric(frame[right],errors='coerce')
                    usable |= a.between(0,100) & b.between(0,100) & (a+b).between(99,101)
                frame = frame.loc[usable]
                summary['split_games'] = int(frame['Game ID'].nunique())
                if not frame.empty:
                    observed = pd.to_datetime(frame['Snapshot Time UTC'],utc=True).max().isoformat()
                    records = market_records(annotate_sharp_money_signals(frame,board),actor='github_actions')
                    for row in records:row['capture_trigger']='scheduled_live'
                    if not dry_run:
                        verified_upsert(client,'cbb_owner_betting_splits',records,batch_size=100)
                    summary.update(rows_written=0 if dry_run else len(records),parsed_rows=len(records),feed_state='reported')
        values = dict(status='completed',completed_at=datetime.now(timezone.utc).isoformat(),provider_observed_at=observed,**{k:v for k,v in summary.items() if k!='parsed_rows'})
        if not dry_run:client.table(RUNS).update(values).eq('id',run_id).execute()
        return dict(id=run_id,dry_run=dry_run,**summary)
    except Exception as exc:
        error = _safe_error(exc)
        if not dry_run:
            client.table(RUNS).update({'status':'failed','completed_at':datetime.now(timezone.utc).isoformat(),'error_summary':error}).eq('id',run_id).execute()
        raise RuntimeError('CBB split capture failed: '+error) from None
