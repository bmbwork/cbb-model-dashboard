"""Arm hourly CBB collection only when an actual upcoming board exists."""
from __future__ import annotations
import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


def has_upcoming_board(rows: list[dict], today: date, horizon_days: int = 14) -> bool:
    end = today + timedelta(days=horizon_days)
    for row in rows:
        try:
            day = date.fromisoformat(str(row['slate_date']))
            count = int(row.get('board_rows') or 0)
        except (ValueError, TypeError, KeyError):
            continue
        if today <= day <= end and count > 0:
            return True
    return False


def owls_credential_shape(value: str | None) -> str:
    """Diagnostic category only. Never emit keys, hashes, prefixes or lengths."""
    raw = str(value or "").strip()
    if not raw:
        return "missing"
    if raw.lower().startswith("bearer "):
        return "bearer_prefix_in_secret"
    if raw.startswith(('"', "'")) or raw.endswith(('"', "'")):
        return "quoted_secret"
    if re.fullmatch(r"owlsinsight_[0-9a-fA-F]{64}", raw):
        return "expected"
    return "unexpected"


def main():
    from supabase import create_client
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_SECRET_KEY')
    if not key:
        raise RuntimeError('CBB market scheduler requires a server credential')
    today = datetime.now(ZoneInfo('America/Chicago')).date()
    client = create_client(os.environ['SUPABASE_URL'], key)
    rows = client.table('cbb_slates').select('slate_date,board_rows').gte('slate_date', today.isoformat()).lte('slate_date', (today + timedelta(days=14)).isoformat()).gt('board_rows', 0).limit(1).execute().data or []
    active = has_upcoming_board(rows, today)
    if os.environ.get('GITHUB_OUTPUT'):
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as handle:
            handle.write('active=' + str(active).lower() + '\n')
    key_shape = owls_credential_shape(os.environ.get('OWLS_INSIGHT_API_KEY'))
    print(json.dumps({'active': active, 'date_chicago': today.isoformat(),
                      'reason': 'upcoming_published_slate' if active else 'no_upcoming_published_slate',
                      'provider_key_configured': key_shape != 'missing',
                      'provider_key_format': key_shape}))
    # A live request on 2026-11-02 authenticated successfully even though
    # the diagnostic shape classifier returned "unexpected". This shape is
    # informational, NOT a source of truth about credential validity.
    # Let Owls decide whether a present key is valid; fail closed if absent.
    if active and key_shape == 'missing':
        raise RuntimeError(
            'Upcoming CBB slate exists but OWLS_INSIGHT_API_KEY is missing.'
        )


if __name__ == '__main__':
    main()
