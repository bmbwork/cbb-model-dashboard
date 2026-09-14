from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_storage_import_does_not_initialize_dashboard_ui_runtime():
    code = r'''
import sys
from cbb_dashboard.storage import StoreConfig, SupabaseSlateStore
assert "cbb_dashboard.premium_ui_patch" not in sys.modules
assert "cbb_dashboard.conference_filter_runtime" not in sys.modules
print("headless storage import ok")
'''
    env = dict(os.environ)
    env["STAT_FACTORY_HEADLESS_AUTOMATION"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "headless storage import ok" in result.stdout
