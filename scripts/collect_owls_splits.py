"""Collect current provider splits into the private archive; counts-only output."""
import argparse,json,os
from supabase import create_client
from cbb_dashboard.owlsinsight_provider import OwlsInsightConfig,OwlsInsightSplitsProvider
from cbb_dashboard.split_collection import collect_owls_splits

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--dry-run',action='store_true');args=parser.parse_args()
    key=os.environ.get('SUPABASE_SECRET_KEY') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    if not key:raise RuntimeError('CBB server credential is missing')
    if not args.dry_run and os.environ.get('GITHUB_REF')!='refs/heads/main':raise RuntimeError('CBB split writes require main')
    db=create_client(os.environ['SUPABASE_URL'],key)
    provider=OwlsInsightSplitsProvider(OwlsInsightConfig(os.environ['OWLS_INSIGHT_API_KEY']))
    print(json.dumps(collect_owls_splits(db,provider,dry_run=args.dry_run),sort_keys=True))
