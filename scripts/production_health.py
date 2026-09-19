from __future__ import annotations

import json
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from supabase import create_client

TZ=ZoneInfo("America/Chicago")
MAX_SLATE_AGE_DAYS=4


def active_window(day: date) -> bool:
    if day.month in {11,12,1,2,3}:
        return True
    return day.month == 4 and day.day <= 10


def main() -> int:
    local=datetime.now(TZ)
    day=local.date()
    if not active_window(day):
        print(json.dumps({"status":"healthy_offseason_idle","date":day.isoformat()}))
        return 0

    url=str(os.environ.get("SUPABASE_URL") or "").strip()
    key=str(os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        raise RuntimeError("CBB production-health Supabase secrets are not configured")
    client=create_client(url,key)
    rows=(client.table("cbb_slate_revisions")
          .select("slate_date,revision,archived_at")
          .order("slate_date",desc=True)
          .order("revision",desc=True)
          .limit(1).execute().data or [])
    if not rows:
        if day.month == 11 and day.day <= 10:
            print(json.dumps({"status":"healthy_season_startup_no_slate_yet","date":day.isoformat()}))
            return 0
        raise RuntimeError("No CBB published slate revisions exist during the active season")
    latest=rows[0]
    slate=date.fromisoformat(str(latest["slate_date"]))
    age=(day-slate).days
    if age > MAX_SLATE_AGE_DAYS:
        raise RuntimeError(
            f"CBB published slate is stale: slate={slate.isoformat()} age_days={age}"
        )
    print(json.dumps({"status":"healthy","latest":latest,"slate_age_days":age},default=str,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
