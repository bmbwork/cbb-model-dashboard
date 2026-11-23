"""Collect current provider splits into the private archive; counts-only output."""
import argparse,json,os
from supabase import create_client
from cbb_dashboard.owlsinsight_provider import OwlsInsightConfig,OwlsInsightSplitsProvider
from cbb_dashboard.split_collection import collect_owls_splits
from cbb_dashboard.recovery import PipelineRun,AlreadyRunning

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--dry-run',action='store_true');args=parser.parse_args()
    key=os.environ.get('SUPABASE_SECRET_KEY') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    if not key:raise RuntimeError('CBB server credential is missing')
    if not args.dry_run and os.environ.get('GITHUB_REF')!='refs/heads/main':raise RuntimeError('CBB split writes require main')
    db=create_client(os.environ['SUPABASE_URL'],key)
    provider=OwlsInsightSplitsProvider(OwlsInsightConfig(os.environ['OWLS_INSIGHT_API_KEY']))
    if args.dry_run:
        print(json.dumps(collect_owls_splits(db,provider,dry_run=True),sort_keys=True))
    else:
        try:
            with PipelineRun(db,'splits') as run:
                result=collect_owls_splits(db,provider)
                run.rows=result['rows_written'];run.details=result
                run.status='idle' if result['feed_state']=='idle' else 'completed'
        except AlreadyRunning:
            print(json.dumps({'stage':'splits','status':'already_running'}))
