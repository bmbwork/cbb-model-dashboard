from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _eligible(frame: pd.DataFrame) -> pd.DataFrame:
    mask = frame.get("Grade Eligible", pd.Series(True, index=frame.index)).fillna(False).astype(bool)
    if "Primary Evaluation Eligible" in frame.columns:
        mask &= frame["Primary Evaluation Eligible"].fillna(False).astype(bool)
    elif "D1 Evaluation Eligible" in frame.columns:
        mask &= frame["D1 Evaluation Eligible"].fillna(False).astype(bool)
    return frame.loc[mask].copy()


def slate_grade_metrics(graded: pd.DataFrame) -> dict[str, Any]:
    primary = _eligible(graded)
    out: dict[str, Any] = {
        "games": int(len(primary)),
        "winner_accuracy": float(pd.to_numeric(primary.get("Model Winner Correct"), errors="coerce").mean()) if len(primary) else np.nan,
        "brier": float(pd.to_numeric(primary.get("Brier Component"), errors="coerce").mean()) if len(primary) else np.nan,
        "log_loss": float(pd.to_numeric(primary.get("Log Loss Component"), errors="coerce").mean()) if len(primary) else np.nan,
        "margin_mae": float(pd.to_numeric(primary.get("Absolute Margin Error"), errors="coerce").mean()) if len(primary) else np.nan,
        "total_mae": float(pd.to_numeric(primary.get("Absolute Total Error"), errors="coerce").mean()) if len(primary) and "Absolute Total Error" in primary.columns else np.nan,
    }
    if "V1.0.1 Baseline Winner Correct" in primary.columns:
        out.update({
            "baseline_winner_accuracy": float(pd.to_numeric(primary["V1.0.1 Baseline Winner Correct"], errors="coerce").mean()),
            "baseline_brier": float(pd.to_numeric(primary.get("V1.0.1 Baseline Brier Component"), errors="coerce").mean()),
            "baseline_margin_mae": float(pd.to_numeric(primary.get("V1.0.1 Baseline Absolute Margin Error"), errors="coerce").mean()),
        })
        out["winner_accuracy_delta"] = out["winner_accuracy"] - out["baseline_winner_accuracy"]
        out["brier_delta"] = out["brier"] - out["baseline_brier"]
        out["margin_mae_improvement"] = out["baseline_margin_mae"] - out["margin_mae"]
    return out


def history_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in records:
        grading = record.get("grading_json") or []
        if not grading:
            continue
        frame = pd.DataFrame(grading)
        if frame.empty:
            continue
        metrics = slate_grade_metrics(frame)
        rows.append({
            "Slate Date": str(record.get("slate_date") or ""),
            "Model Version": str(record.get("model_version") or ""),
            "Games": metrics.get("games"),
            "Winner Accuracy": metrics.get("winner_accuracy"),
            "Brier": metrics.get("brier"),
            "Log Loss": metrics.get("log_loss"),
            "Margin MAE": metrics.get("margin_mae"),
            "Total MAE": metrics.get("total_mae"),
            "V1.0.1 Winner Accuracy": metrics.get("baseline_winner_accuracy"),
            "V1.0.1 Brier": metrics.get("baseline_brier"),
            "V1.0.1 Margin MAE": metrics.get("baseline_margin_mae"),
            "Margin MAE Improvement": metrics.get("margin_mae_improvement"),
        })
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["Slate Date"] = pd.to_datetime(out["Slate Date"], errors="coerce")
    return out.sort_values("Slate Date")


def combined_graded_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for record in records:
        grading = record.get("grading_json") or []
        if grading:
            frame = pd.DataFrame(grading)
            frame["_slate_date"] = str(record.get("slate_date") or "")
            frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def aggregate_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    combined = combined_graded_frame(records)
    if combined.empty:
        return {"games": 0}
    return slate_grade_metrics(combined)


def confidence_buckets(records: list[dict[str, Any]]) -> pd.DataFrame:
    combined = combined_graded_frame(records)
    if combined.empty:
        return pd.DataFrame()
    primary = _eligible(combined)
    p = pd.to_numeric(primary.get("Win Probability"), errors="coerce")
    correct = pd.to_numeric(primary.get("Model Winner Correct"), errors="coerce")
    bins = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.000001]
    labels = ["50–55%", "55–60%", "60–65%", "65–70%", "70–75%", "75–80%", "80–85%", "85–90%", "90–95%", "95%+"]
    bucket = pd.cut(p, bins=bins, labels=labels, right=False, include_lowest=True)
    tmp = pd.DataFrame({"Bucket": bucket, "Correct": correct, "Prediction": p}).dropna(subset=["Bucket", "Correct", "Prediction"])
    if tmp.empty:
        return pd.DataFrame()
    out = tmp.groupby("Bucket", observed=False).agg(
        Games=("Correct", "size"),
        Actual_Win_Rate=("Correct", "mean"),
        Avg_Prediction=("Prediction", "mean"),
    ).reset_index()
    out = out[out["Games"] > 0].copy()
    return out


def top_k_summary(records: list[dict[str, Any]], cutoffs=(5, 10, 25)) -> pd.DataFrame:
    combined = combined_graded_frame(records)
    if combined.empty:
        return pd.DataFrame()
    rows = []
    for k in cutoffs:
        hits = 0.0
        games = 0
        for _, group in combined.groupby("_slate_date"):
            primary = _eligible(group)
            rank_col = "D1 Rank" if "D1 Rank" in primary.columns else "Rank"
            ranked = primary.assign(_r=pd.to_numeric(primary[rank_col], errors="coerce")).sort_values("_r").head(k)
            hits += float(pd.to_numeric(ranked.get("Model Winner Correct"), errors="coerce").fillna(0).sum())
            games += len(ranked)
        rows.append({"Cutoff": f"Top {k}", "Correct": int(hits), "Games": games, "Accuracy": hits / games if games else np.nan})
    return pd.DataFrame(rows)
