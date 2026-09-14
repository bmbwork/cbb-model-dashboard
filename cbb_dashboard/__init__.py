"""CBB Model Dashboard package.

Dashboard UI patches remain enabled for normal imports. Background automation
scripts can import storage/data helpers without pulling the Streamlit/UI stack.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys


def _is_headless_automation() -> bool:
    forced = str(os.environ.get("STAT_FACTORY_HEADLESS_AUTOMATION", "") or "").strip().lower()
    if forced in {"1", "true", "yes", "on"}:
        return True
    try:
        script = Path(sys.argv[0]).expanduser()
    except Exception:
        return False
    return script.suffix == ".py" and script.parent.name == "scripts"


if not _is_headless_automation():
    from .conference_filter_runtime import install_conference_filter_runtime as _install_conference_filter_runtime
    from .premium_ui_patch import apply_premium_ui_patch as _apply_premium_ui_patch

    _apply_premium_ui_patch()
    _install_conference_filter_runtime()
