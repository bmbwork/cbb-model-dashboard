from __future__ import annotations

import json
import os

from cbb_dashboard.public_consensus import collect_public_consensus
from cbb_dashboard.recovery import PipelineRun,AlreadyRunning


def main() -> int:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    from supabase import create_client
    client=create_client(url,key)
    with PipelineRun(client,'consensus') as run:
        result=collect_public_consensus(client)
        run.rows=result['stored_rows'];run.details={'stored_rows':result['stored_rows'],'requested_games':result.get('requested_games',0)}
        run.status='idle' if not result.get('requested_games') else 'completed'
        print(json.dumps(result,default=str,sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AlreadyRunning:
        print(json.dumps({'stage':'consensus','status':'already_running'}))
