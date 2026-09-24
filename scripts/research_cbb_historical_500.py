#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cbb_dashboard.final_results import fetch_scores, grade_frozen_board
from cbb_dashboard.performance import slate_grade_metrics

EXPECTED_MODEL = "1.1.3B"
SEED = 20260924


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Read-only CBB V1.1.3B historical effectiveness replay.")
    p.add_argument("--model-root", required=True)
    p.add_argument("--start", default="2025-11-03")
    p.add_argument("--end", default="2026-03-08")
    p.add_argument("--max-games", type=int, default=500)
    p.add_argument("--output-dir", default="research-output/cbb-historical-500")
    return p.parse_args()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_log(text: str, secret: str) -> str:
    out = text or ""
    if secret:
        out = out.replace(secret, "[REDACTED]")
    return out[-8000:]


def candidate_dates(start: str, end: str) -> list[str]:
    # Primary pass spans the whole season and rotates weekdays.
    primary = list(pd.date_range(start=start, end=end, freq="6D"))
    # Secondary pass fills gaps only if the primary pass does not yield 500 eligible games.
    secondary_start = pd.Timestamp(start) + pd.Timedelta(days=3)
    secondary = list(pd.date_range(start=secondary_start, end=end, freq="12D"))
    ordered = []
    seen = set()
    for value in primary + secondary:
        day = value.date().isoformat()
        if day not in seen:
            seen.add(day)
            ordered.append(day)
    return ordered


def locate_board(model_root: Path, day: str) -> Path | None:
    expected = model_root / "outputs" / day / "latest" / f"cbb_decision_board_{day}.csv"
    if expected.exists() and expected.stat().st_size > 0:
        return expected
    matches = sorted((model_root / "outputs" / day).rglob("*.csv")) if (model_root / "outputs" / day).exists() else []
    preferred = [p for p in matches if "decision_board" in p.name.lower()]
    return preferred[0] if preferred else (matches[0] if matches else None)


def run_day(model_root: Path, day: str, key: str, log_dir: Path) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    cmd = ["bash", str(model_root / "run_cbb_champion.sh"), "--date", day]
    proc = subprocess.run(cmd, cwd=model_root, text=True, capture_output=True, env=os.environ.copy())
    log_path = log_dir / f"{day}.log"
    log_path.write_text(
        "STDOUT\n" + clean_log(proc.stdout, key) + "\n\nSTDERR\n" + clean_log(proc.stderr, key),
        encoding="utf-8",
    )
    status: dict[str, Any] = {"date": day, "return_code": proc.returncode, "log": str(log_path)}
    if proc.returncode == 3:
        status["status"] = "no_modelable_games"
        return None, status
    if proc.returncode != 0:
        status["status"] = "model_failed"
        return None, status

    board_path = locate_board(model_root, day)
    if board_path is None:
        status["status"] = "missing_board"
        return None, status

    board = pd.read_csv(board_path, low_memory=False)
    status["board_rows"] = int(len(board))
    status["board_path"] = str(board_path)

    model_col = next((c for c in ["Model Version", "model_version", "MODEL_VERSION"] if c in board.columns), None)
    if model_col:
        versions = sorted({str(v).strip() for v in board[model_col].dropna().unique()})
        status["model_versions"] = versions
        if versions and not all(EXPECTED_MODEL.lower() in v.lower() for v in versions):
            status["status"] = "wrong_model_version"
            return None, status

    scores = fetch_scores(day, key)
    graded = grade_frozen_board(board, scores, pd.DataFrame())
    eligible = graded.get("Grade Eligible", pd.Series(False, index=graded.index)).fillna(False).astype(bool)
    if "Primary Evaluation Eligible" in graded.columns:
        eligible &= graded["Primary Evaluation Eligible"].fillna(False).astype(bool)
        status["d1_filter"] = "Primary Evaluation Eligible"
    elif "D1 Evaluation Eligible" in graded.columns:
        d1 = graded["D1 Evaluation Eligible"].map(lambda x: str(x).lower() in {"true", "1", "1.0"})
        eligible &= d1
        status["d1_filter"] = "D1 Evaluation Eligible"
    else:
        status["d1_filter"] = "unavailable"

    out = graded.loc[eligible].copy()
    out["_replay_date"] = day
    status["eligible_games"] = int(len(out))
    status["status"] = "graded"
    return out, status


def even_cap(frame: pd.DataFrame, max_games: int) -> pd.DataFrame:
    if len(frame) <= max_games:
        return frame.copy()
    ordered = frame.copy()
    game_id = pd.to_numeric(ordered.get("Game ID"), errors="coerce")
    ordered["_sort_game_id"] = game_id
    ordered = ordered.sort_values(["_replay_date", "_sort_game_id"], kind="stable").reset_index(drop=True)
    raw = np.linspace(0, len(ordered) - 1, num=max_games)
    idx = np.unique(np.rint(raw).astype(int)).tolist()
    if len(idx) < max_games:
        selected = set(idx)
        for i in range(len(ordered)):
            if i not in selected:
                idx.append(i)
                selected.add(i)
                if len(idx) == max_games:
                    break
    idx = sorted(idx[:max_games])
    return ordered.iloc[idx].drop(columns=["_sort_game_id"], errors="ignore").reset_index(drop=True)


def ece_home_probability(frame: pd.DataFrame, bins: int = 10) -> float | None:
    if "Home Win Probability" not in frame.columns or "Home Win Actual" not in frame.columns:
        return None
    p = pd.to_numeric(frame["Home Win Probability"], errors="coerce")
    y = pd.to_numeric(frame["Home Win Actual"], errors="coerce")
    valid = p.notna() & y.notna()
    p, y = p[valid], y[valid]
    if p.empty:
        return None
    bucket = pd.cut(p, bins=np.linspace(0, 1, bins + 1), include_lowest=True, right=True)
    tmp = pd.DataFrame({"p": p, "y": y, "bucket": bucket})
    total = len(tmp)
    error = 0.0
    for _, g in tmp.groupby("bucket", observed=False):
        if g.empty:
            continue
        error += (len(g) / total) * abs(float(g["p"].mean()) - float(g["y"].mean()))
    return float(error)


def month_metrics(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    tmp = frame.copy()
    tmp["_month"] = pd.to_datetime(tmp["_replay_date"], errors="coerce").dt.strftime("%Y-%m")
    rows = []
    for month, group in tmp.groupby("_month", dropna=False):
        metrics = slate_grade_metrics(group)
        rows.append({"month": str(month), **metrics})
    return rows


def confidence_table(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if "Win Probability" not in frame.columns or "Model Winner Correct" not in frame.columns:
        return []
    p = pd.to_numeric(frame["Win Probability"], errors="coerce")
    c = pd.to_numeric(frame["Model Winner Correct"], errors="coerce")
    bins = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.000001]
    labels = ["50-55%", "55-60%", "60-65%", "65-70%", "70-75%", "75-80%", "80-85%", "85-90%", "90-95%", "95%+"]
    bucket = pd.cut(p, bins=bins, labels=labels, right=False, include_lowest=True)
    tmp = pd.DataFrame({"bucket": bucket, "correct": c, "prediction": p}).dropna()
    rows = []
    for label, group in tmp.groupby("bucket", observed=False):
        if group.empty:
            continue
        rows.append({
            "bucket": str(label),
            "games": int(len(group)),
            "actual_accuracy": float(group["correct"].mean()),
            "avg_model_confidence": float(group["prediction"].mean()),
        })
    return rows


def main() -> int:
    args = parse_args()
    if args.max_games < 1 or args.max_games > 500:
        raise SystemExit("--max-games must be between 1 and 500")

    key = str(os.environ.get("CBBD_API_KEY") or "").strip()
    if not key:
        raise SystemExit("CBBD_API_KEY is required")

    model_root = Path(args.model_root).resolve()
    runner = model_root / "run_cbb_champion.sh"
    source = model_root / "ACTIVE_CBB_Prediction_Engine_V1_1_3B_CHAMPION.py"
    if not runner.exists() or not source.exists():
        raise SystemExit("Frozen V1.1.3B runtime is incomplete")

    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = out_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    all_frames: list[pd.DataFrame] = []
    date_log: list[dict[str, Any]] = []
    primary_count = len(list(pd.date_range(start=args.start, end=args.end, freq="6D")))

    dates = candidate_dates(args.start, args.end)
    for i, day in enumerate(dates):
        # Run the full season-spanning primary pass before considering whether a fill pass is needed.
        if i >= primary_count and sum(len(x) for x in all_frames) >= args.max_games:
            date_log.append({"date": day, "status": "secondary_not_needed"})
            continue
        frame, status = run_day(model_root, day, key, log_dir)
        date_log.append(status)
        if frame is not None and not frame.empty:
            all_frames.append(frame)

    combined = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()
    if combined.empty:
        (out_dir / "cbb_historical_500_date_log.json").write_text(json.dumps(date_log, indent=2), encoding="utf-8")
        raise SystemExit("No eligible historical games were produced")

    sample = even_cap(combined, args.max_games)
    metrics = slate_grade_metrics(sample)
    metrics["ece_home_probability_10bin"] = ece_home_probability(sample)

    cutoff_cols = [c for c in sample.columns if "cutoff" in c.lower() or "feature" in c.lower() and "time" in c.lower()]
    version_cols = [c for c in sample.columns if "version" in c.lower()]
    observed_versions: dict[str, list[str]] = {}
    for col in version_cols:
        observed_versions[col] = sorted({str(v) for v in sample[col].dropna().unique()})[:20]

    summary = {
        "test_name": "CBB V1.1.3B historical effectiveness replay",
        "model_expected": EXPECTED_MODEL,
        "design": "read-only retrospective replay; market data excluded",
        "date_range": {"start": args.start, "end": args.end},
        "candidate_dates": dates,
        "dates_attempted": sum(1 for row in date_log if row.get("status") != "secondary_not_needed"),
        "dates_graded": sum(1 for row in date_log if row.get("status") == "graded"),
        "eligible_games_before_cap": int(len(combined)),
        "evaluated_games": int(len(sample)),
        "max_games": int(args.max_games),
        "selection_after_replay": "chronologically even deterministic cap across all eligible replay rows",
        "primary_population": "verified final Division I games when D1 eligibility is present in the board",
        "metrics": metrics,
        "metrics_by_month": month_metrics(sample),
        "confidence_buckets": confidence_table(sample),
        "observed_model_versions": observed_versions,
        "timing_columns_present": cutoff_cols,
        "source_sha256": sha256_file(source),
        "market_inputs_used_by_harness": False,
        "publication_writes": False,
        "causality_note": (
            "This workflow is a retrospective replay. Treat the result as a production-quality historical "
            "backtest only if the frozen champion's date-specific feature construction is confirmed to use "
            "information available before each target game's forecast cutoff. The harness never feeds odds, "
            "splits, closing lines, or outcomes into the predictor."
        ),
    }

    sample.to_csv(out_dir / "cbb_historical_500_games.csv", index=False)
    pd.DataFrame(date_log).to_csv(out_dir / "cbb_historical_500_date_log.csv", index=False)
    (out_dir / "cbb_historical_500_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "complete",
        "eligible_games_before_cap": len(combined),
        "evaluated_games": len(sample),
        "metrics": metrics,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Research workflow credential fallback trigger: 2026-09-24
