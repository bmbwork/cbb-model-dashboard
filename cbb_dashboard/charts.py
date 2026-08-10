from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

BG = "rgba(0,0,0,0)"
GRID = "rgba(231,203,188,.10)"
TEXT = "#e8d9d0"
MUTED = "#a99287"
ACCENT = "#f97316"
TEAL = "#2dd4bf"
BASE = "#8b7b73"


def _layout(fig: go.Figure, title: str = "") -> go.Figure:
    fig.update_layout(
        title=title,
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(color=TEXT),
        margin=dict(l=30, r=20, t=48 if title else 22, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hoverlabel=dict(bgcolor="#211419", font_color="#fff7ed"),
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig


def confidence_chart(board: pd.DataFrame, top_n: int = 25) -> go.Figure:
    data = board.nsmallest(min(top_n, len(board)), "_rank").copy().sort_values("_win_prob")
    labels = data["Model Pick"].astype(str) + " vs " + np.where(
        data["Model Pick"].astype(str).eq(data["Home Team"].astype(str)),
        data["Away Team"].astype(str), data["Home Team"].astype(str)
    )
    fig = go.Figure(go.Bar(
        x=data["_win_prob"] * 100,
        y=labels,
        orientation="h",
        marker_color=ACCENT,
        customdata=np.c_[data["Fair Spread"]],
        hovertemplate="%{y}<br>Win probability %{x:.1f}%<br>Model line %{customdata[0]:+.1f}<extra></extra>",
    ))
    fig.update_xaxes(title="Model win probability", ticksuffix="%", range=[50, max(100, float((data["_win_prob"]*100).max()) + 2)])
    return _layout(fig, f"Top {min(top_n, len(data))} projection strength")


def team_comparison_chart(row: pd.Series) -> go.Figure:
    """Raw adjusted-efficiency comparison without mixing SOS onto the same axis."""
    home = str(row.get("Home Team"))
    away = str(row.get("Away Team"))
    metrics = ["AdjO", "AdjD", "AdjNet"]
    hv = [row.get("Home AdjO"), row.get("Home AdjD"), row.get("Home AdjNet")]
    av = [row.get("Away AdjO"), row.get("Away AdjD"), row.get("Away AdjNet")]
    fig = go.Figure()
    fig.add_trace(go.Bar(name=away, x=metrics, y=av, marker_color=BASE))
    fig.add_trace(go.Bar(name=home, x=metrics, y=hv, marker_color=ACCENT))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="Points per 100 possessions / net margin")
    return _layout(fig, "Adjusted efficiency profile · AdjD lower is better")


def challenger_comparison_chart(row: pd.Series) -> go.Figure:
    challenger = abs(float(pd.to_numeric(row.get("Projected Winner Margin"), errors="coerce") or 0))
    baseline = abs(float(pd.to_numeric(row.get("V1.0.1 Baseline Projected Winner Margin"), errors="coerce") or 0))
    fig = go.Figure()
    fig.add_trace(go.Bar(x=["V1.0.1", str(row.get("Model Version") or "Published")], y=[baseline, challenger], marker_color=[BASE, ACCENT], text=[f"{baseline:.1f}", f"{challenger:.1f}"], textposition="outside"))
    fig.update_yaxes(title="Projected winner margin")
    return _layout(fig, "Projected margin: anchor vs published model")


def performance_trend(history: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=history["Slate Date"], y=history["Margin MAE"], mode="lines+markers", name="Production model", line=dict(color=ACCENT)))
    fig.update_yaxes(title="Margin MAE (points)")
    return _layout(fig, "Production margin error by slate")


def calibration_chart(buckets: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=buckets["Avg_Prediction"]*100, y=buckets["Actual_Win_Rate"]*100, mode="lines+markers", name="Observed", line=dict(color=TEAL)))
    fig.add_trace(go.Scatter(x=[50,100], y=[50,100], mode="lines", name="Perfect calibration", line=dict(color=BASE, dash="dash")))
    fig.update_xaxes(title="Average predicted win probability", ticksuffix="%", range=[50,100])
    fig.update_yaxes(title="Observed win rate", ticksuffix="%", range=[0,100])
    return _layout(fig, "Confidence calibration")
