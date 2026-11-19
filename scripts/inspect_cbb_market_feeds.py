"""Read-only feed diagnostics. Log schema/counts only, never keys or raw payloads."""
import json
import os
import re
from datetime import datetime, timezone
from supabase import create_client
from cbb_dashboard.public_consensus import _active_board
from cbb_dashboard.owlsinsight_provider import OwlsInsightConfig, OwlsInsightSplitsProvider
from cbb_dashboard.owlsinsight_odds_provider import OwlsInsightOddsConfig, OwlsInsightOddsProvider


def shape(value, depth=0):
    if depth>3:return type(value).__name__
    if isinstance(value,dict):return {str(k)[:50]:shape(v,depth+1) for k,v in list(value.items())[:16]}
    if isinstance(value,list):return {'count':len(value),'item':shape(value[0],depth+1) if value else None}
    return type(value).__name__


def main():
    db=create_client(os.environ['SUPABASE_URL'],os.environ.get('SUPABASE_SECRET_KEY') or os.environ['SUPABASE_SERVICE_ROLE_KEY'])
    board=_active_board(db,datetime.now(timezone.utc));key=os.environ['OWLS_INSIGHT_API_KEY']
    for name,provider,fetch in [('splits',OwlsInsightSplitsProvider(OwlsInsightConfig(key)),'live_splits'),('odds',OwlsInsightOddsProvider(OwlsInsightOddsConfig(key)),'current_odds')]:
        try:
            payload=getattr(provider,fetch)()
            if name=='splits':
                frame,health=provider.parse(payload,board); summary={k:health[k] for k in ('board_games','provider_events','mapped_games','split_games','split_rows')}
            else:
                events=provider._coalesce_events(payload);matched=provider.map_board_games(board,events)
                summary={'board_games':len(board),'provider_events':len(events),'mapped_games':len(matched)}
            print(json.dumps({'feed':name,'payload_shape':shape(payload),'summary':summary}),flush=True)
        except Exception as exc:
            statuses=re.findall(r'\b(?:401|403|404|429|500|502|503|504)\b',str(exc))
            print(json.dumps({'feed':name,'error_type':type(exc).__name__,'http_status':statuses[0] if statuses else None}),flush=True)

if __name__=='__main__':main()
