from __future__ import annotations

import pandas as pd

from cbb_dashboard.performance import aggregate_metrics, confidence_buckets, slate_grade_metrics, top_k_summary


def graded_frame():
    return pd.DataFrame([
        {"Rank":1,"D1 Rank":1,"Grade Eligible":True,"Primary Evaluation Eligible":True,"Win Probability":.80,"Model Winner Correct":1,"Absolute Margin Error":4.0,"Absolute Total Error":8.0,"Brier Component":.04,"Log Loss Component":.22,"V1.0.1 Baseline Winner Correct":1,"V1.0.1 Baseline Absolute Margin Error":7.0,"V1.0.1 Baseline Brier Component":.09,"V1.0.1 Baseline Log Loss Component":.30},
        {"Rank":2,"D1 Rank":2,"Grade Eligible":True,"Primary Evaluation Eligible":True,"Win Probability":.60,"Model Winner Correct":0,"Absolute Margin Error":10.0,"Absolute Total Error":12.0,"Brier Component":.36,"Log Loss Component":.92,"V1.0.1 Baseline Winner Correct":0,"V1.0.1 Baseline Absolute Margin Error":11.0,"V1.0.1 Baseline Brier Component":.35,"V1.0.1 Baseline Log Loss Component":.90},
    ])


def test_slate_metrics_compare_baseline():
    m = slate_grade_metrics(graded_frame())
    assert m["games"] == 2
    assert m["winner_accuracy"] == .5
    assert m["margin_mae"] == 7.0
    assert m["baseline_margin_mae"] == 9.0
    assert m["margin_mae_improvement"] == 2.0


def test_aggregate_and_topk():
    records = [{"slate_date":"2026-01-10","model_version":"1.1.0","grading_json":graded_frame().to_dict("records")}]
    assert aggregate_metrics(records)["games"] == 2
    top = top_k_summary(records, cutoffs=(1,2))
    assert top.loc[top["Cutoff"].eq("Top 1"), "Accuracy"].iloc[0] == 1.0
    assert not confidence_buckets(records).empty
