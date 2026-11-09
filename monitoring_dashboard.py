"""Optional Streamlit version of the dashboard (Sub-module 6.6). Run: streamlit run monitoring_dashboard.py"""
import os

import streamlit as st

import monitoring_core as core

st.set_page_config(page_title="Model Monitor", layout="wide")
st.title("Model Monitoring Dashboard")
days = st.sidebar.selectbox("Time window (days)", [7, 14, 30, 90], index=2)


@st.cache_data(ttl=300)
def load_cached(days: int):
    return core.load(days)


if not os.path.exists(core.db_path()):
    st.warning("No log database found. Run the API, or run simulate_logs.py first.")
    st.stop()
df = load_cached(days)
if df.empty:
    st.warning("No predictions logged in this time window.")
    st.stop()
if (df["is_simulated"] == 1).any():
    st.warning("This dashboard includes SIMULATED data. It is not real production traffic.")

items = list(core.indicators(df).items())
for start in (0, 3):
    for col, (label, value) in zip(st.columns(3), items[start:start + 3]):
        col.metric(label, value)

st.subheader("Alerts")
alerts, note = core.check_alerts(df)
if note:
    st.info(note)
for level, text in alerts:
    (st.error if level == "High" else st.warning if level == "Medium" else st.info)(f"{level}: {text}")
if not alerts and not note:
    st.success("No alerts: all indicators are within their thresholds.")

charts = core.make_charts(df)
left, right = st.columns(2)
left.plotly_chart(charts["volume"], width="stretch")
right.plotly_chart(charts["scores"], width="stretch")
left.plotly_chart(charts["flag_rate"], width="stretch")
right.plotly_chart(charts["latency"], width="stretch")
st.plotly_chart(charts["errors"], width="stretch")
if "calibration" in charts:
    st.plotly_chart(charts["calibration"], width="stretch")

st.subheader("Performance on known outcomes")
summary, n_known = core.performance(df)
if summary is None:
    st.info(f"Only {n_known} real outcomes are known so far. Too few to judge performance.")
else:
    for label, value in summary.items():
        st.write(f"**{label}:** {value}")
    st.caption("Flagged students may receive support, which can change their outcome, so these "
               "figures can look better than the model alone would deliver.")
