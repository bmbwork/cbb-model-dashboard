from __future__ import annotations
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_cbb_auto_grade.py"
INSTALLER = ROOT / "scripts" / "install_cbb_auto_grade_launchd.sh"

def load_runner():
    spec = importlib.util.spec_from_file_location("cbb_auto_grade", RUNNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def board():
    return pd.DataFrame({"Game ID":[1,2],"Start Time UTC":["2026-11-10T18:00:00Z","2026-11-10T20:00:00Z"]})

def grading(finals: int, score=75):
    return pd.DataFrame({
        "Game ID":[1,2],
        "Status":["Final" if finals >= 1 else "Halftime", "Final" if finals >= 2 else "Scheduled"],
        "Grade Eligible":[finals >= 1, finals >= 2],
        "Final Away Score":[70 if finals >= 1 else None, 65 if finals >= 2 else None],
        "Final Home Score":[score if finals >= 1 else None, 64 if finals >= 2 else None],
    })

def test_waits_until_game_can_reasonably_finish():
    m=load_runner(); b=board()
    assert not m.is_due_for_poll(b, datetime(2026,11,10,19,20,tzinfo=timezone.utc))
    assert m.is_due_for_poll(b, datetime(2026,11,10,19,30,tzinfo=timezone.utc))

def test_fingerprint_ignores_live_churn_but_detects_finals_and_corrections():
    m=load_runner(); a=grading(0); b=a.copy(); b.loc[0,"Status"]="In Progress"
    assert m.grading_fingerprint(a)==m.grading_fingerprint(b)
    assert m.grading_fingerprint(a)!=m.grading_fingerprint(grading(1))
    assert m.grading_fingerprint(grading(1))!=m.grading_fingerprint(grading(1,76))

def test_settled_requires_terminal_games():
    m=load_runner()
    assert not m.grading_is_settled(grading(1),2)
    assert m.grading_is_settled(grading(2),2)
    c=grading(1); c.loc[1,"Status"]="Canceled"
    assert m.grading_is_settled(c,2)

def test_worker_is_background_and_uses_frozen_grader():
    runner=RUNNER.read_text(); installer=INSTALLER.read_text()
    assert 'model_root / "grade_cbb_champion.sh"' in runner
    assert "store.publish_grading" in runner
    assert "OWLS_INSIGHT_API_KEY" not in runner
    assert '"StartInterval": 1800' in installer
    assert "run_cbb_auto_grade.py" in installer
