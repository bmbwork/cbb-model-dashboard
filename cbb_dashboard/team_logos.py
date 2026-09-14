"""Bundled, verified display logos; no network dependency on a page render."""
from __future__ import annotations

import base64
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets" / "cbb_teams"


def _key(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", text.replace("&", "and"))


@lru_cache(maxsize=1)
def _directory() -> dict[str, dict]:
    try:
        payload = json.loads((ASSET_ROOT / "directory.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    candidates: dict[str, list[dict]] = {}
    for row in payload.get("teams", []):
        for alias in row.get("aliases", []):
            candidates.setdefault(_key(alias), []).append(row)
    return {key: rows[0] for key, rows in candidates.items() if len({r.get("id") for r in rows}) == 1}


@lru_cache(maxsize=1024)
def bundled_logo_source(team: str) -> str:
    record = _directory().get(_key(team))
    if not record:
        return ""
    filename = str(record.get("asset", ""))
    if not re.fullmatch(r"[0-9]+\.png", filename):
        return ""
    try:
        raw = (ASSET_ROOT / filename).read_bytes()
    except OSError:
        return ""
    if not raw.startswith(b"\x89PNG\r\n\x1a\n") or hashlib.sha256(raw).hexdigest() != record.get("sha256"):
        return ""
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
