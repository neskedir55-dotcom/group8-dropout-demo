"""
Monitoring indicators, alert rules and charts, shared by the notebook dashboard and the
optional Streamlit dashboard (Sub-module 6.6, Step 5). Written once, used by both.
"""
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

MIN_RECORDS = 30        # do not draw conclusions from fewer records than this

# Module 5 evaluation on the held-out test set, the reference for real performance
_META = json.loads((Path(__file__).resolve().parent / "model_artifacts" / "model_metadata.json").read_text())
BASELINE_RECALL = _META["test_metrics_at_threshold"]["dropout_recall"]
BASELINE_PRECISION = _META["test_metrics_at_threshold"]["dropout_precision"]


def db_path() -> str:
    return os.getenv("LOG_DB_PATH", "logs/predictions.db")


def load(days: int = 30) -> pd.DataFrame:
    """Read the log rows of the last `days` days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    conn = sqlite3.connect(db_path())
    try:
        df = pd.read_sql("SELECT * FROM predictions WHERE timestamp >= ?", conn,
                         params=(cutoff,))   # a parameter, not pasted into the SQL text
    finally:
        conn.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="ISO8601")
    df["date"] = df["timestamp"].dt.date
    return df


def indicators(df: pd.DataFrame) -> dict:
    """The headline figures, as text ready to display."""
    ok = df[df["status_code"] == 200]
    return {
        "Requests": f"{len(df):,}",
        "Error rate": f"{(df['status_code'] >= 500).mean():.1%}",
        "High-risk flag rate": f"{(ok['decision'] == 'high_risk').mean():.1%}",
        "Average dropout probability": f"{ok['probability'].mean():.1%}",
        "Average latency": f"{df['latency_ms'].mean():.0f} ms",
        "95th percentile latency": f"{df['latency_ms'].quantile(0.95):.0f} ms",
    }


def performance(df: pd.DataFrame):
    """Real performance where the actual outcome is known. Returns (dict or None, n_known)."""
    known = df[df["status_code"] == 200].dropna(subset=["actual_outcome"])
    if len(known) < MIN_RECORDS:
        return None, len(known)
    y_true = known["actual_outcome"].astype(int)
    y_pred = (known["decision"] == "high_risk").astype(int)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    precision = tp / max(int(y_pred.sum()), 1)
    recall = tp / max(int(y_true.sum()), 1)
    return {
        "Predictions with known outcome": f"{len(known):,}",
        "Average predicted dropout probability": f"{known['probability'].mean():.1%}",
        "Actual dropout rate": f"{y_true.mean():.1%}",
        "Dropout precision (flag = predicted dropout)": f"{precision:.1%}  (Module 5 test: {BASELINE_PRECISION:.1%})",
        "Dropout recall": f"{recall:.1%}  (Module 5 test: {BASELINE_RECALL:.1%})",
    }, len(known)


def check_alerts(df: pd.DataFrame):
    """Compare the last 7 days with the period before them. Returns (alerts, note)."""
    alerts = []
    if df.empty:
        return alerts, "The log has no records in this window."
    now = datetime.now(timezone.utc)
    if now - df["timestamp"].max() > timedelta(hours=24):
        alerts.append(("Info", "Logging gap: no records for more than 24 hours."))
    cut = now - timedelta(days=7)
    recent, base = df[df["timestamp"] >= cut], df[df["timestamp"] < cut]
    if len(recent) < MIN_RECORDS or len(base) < MIN_RECORDS:
        return alerts, "Not enough records in both periods to compare. Widen the time window."
    if (recent["status_code"] >= 500).mean() > 0.02:
        alerts.append(("High", "Error rate is above 2% in the last 7 days."))
    if recent["latency_ms"].mean() > 2 * base["latency_ms"].mean():
        alerts.append(("Medium", "Average latency is more than twice the earlier level."))
    r, b = recent[recent["status_code"] == 200], base[base["status_code"] == 200]
    if len(r) >= MIN_RECORDS and len(b) >= MIN_RECORDS:
        shift = (r["decision"] == "high_risk").mean() - (b["decision"] == "high_risk").mean()
        if abs(shift) > 0.10:
            alerts.append(("Medium", f"High-risk flag rate shifted by {shift * 100:+.1f} points."))
        pshift = r["probability"].mean() - b["probability"].mean()
        if abs(pshift) > 0.08:
            alerts.append(("Medium", f"Average dropout probability shifted by {pshift:+.3f}."))
    # Real performance, only when enough outcomes are known
    known = df[df["status_code"] == 200].dropna(subset=["actual_outcome"])
    if len(known) >= MIN_RECORDS:
        y_true = known["actual_outcome"].astype(int)
        y_pred = (known["decision"] == "high_risk").astype(int)
        recall = ((y_pred == 1) & (y_true == 1)).sum() / max(int(y_true.sum()), 1)
        if recall < BASELINE_RECALL - 0.10:
            alerts.append(("High", f"Dropout recall is {recall:.1%}, more than 10 points below the "
                                   f"Module 5 test result ({BASELINE_RECALL:.1%})."))
    return alerts, None


def make_charts(df: pd.DataFrame) -> dict:
    """Six Plotly charts, in a dictionary of name -> figure."""
    import plotly.express as px
    ok = df[df["status_code"] == 200]
    daily = df.groupby("date").agg(
        requests=("id", "count"),
        error_rate=("status_code", lambda s: (s >= 500).mean()),
        latency_mean=("latency_ms", "mean"),
        latency_p95=("latency_ms", lambda s: s.quantile(0.95)),
    ).reset_index()
    flag = ok.groupby("date").agg(flag_rate=("decision", lambda s: (s == "high_risk").mean())).reset_index()
    charts = {
        "volume": px.bar(daily, x="date", y="requests", title="Requests per day"),
        "scores": px.histogram(ok, x="probability", nbins=40, title="Distribution of predicted dropout probabilities"),
        "flag_rate": px.line(flag, x="date", y="flag_rate", title="Daily high-risk flag rate"),
        "latency": px.line(daily, x="date", y=["latency_mean", "latency_p95"], title="Latency per day (ms)"),
        "errors": px.line(daily, x="date", y="error_rate", title="Daily error rate"),
    }
    known = ok.dropna(subset=["actual_outcome"])
    if len(known) >= MIN_RECORDS:
        bands = pd.cut(known["probability"], [0, 0.2, 0.4, 0.6, 0.8, 1.0], include_lowest=True)
        calib = known.groupby(bands, observed=True).agg(
            predicted=("probability", "mean"), actual=("actual_outcome", "mean"), n=("id", "count")).reset_index()
        calib["probability band"] = calib["probability"].astype(str)
        charts["calibration"] = px.bar(calib.melt(id_vars=["probability band", "n"], value_vars=["predicted", "actual"],
                                                   var_name="series", value_name="dropout rate"),
                                       x="probability band", y="dropout rate", color="series", barmode="group",
                                       title="Predicted vs actual dropout rate (known outcomes)")
    return charts
