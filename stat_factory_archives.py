"""Read-only publication archive helpers. No forecast/model writes."""
from __future__ import annotations


def catalog(client, table):
    rows, start = [], 0
    while True:
        batch = client.table(table).select("slate_date,revision,model_version,published_at,board_rows,board_sha256").order("slate_date", desc=True).range(start, start + 999).execute().data or []
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
        start += 1000


def revisions(client, table, day):
    return client.table(table).select("slate_date,revision,board_sha256").eq("slate_date", str(day)).order("revision", desc=True).execute().data or []


def revision(client, table, day, number):
    rows = client.table(table).select("record").eq("slate_date", str(day)).eq("revision", int(number)).limit(1).execute().data or []
    return rows[0]["record"] if rows else None
