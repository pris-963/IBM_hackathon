
import os

import pandas as pd
import requests
import streamlit as st


API_URL = os.getenv(
    "SAFETY_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

st.set_page_config(
    page_title="Safety Layer Dashboard",
    page_icon="🛡️",
    layout="wide",
)

st.title("Dynamic, Exposed-Only Safety Layer")
st.caption(
    "Environmental monitoring, unusual-event detection, "
    "and authenticated safety alerts"
)


@st.cache_data(ttl=5)
def fetch_alerts():
    """Retrieve recent alert metadata from the FastAPI backend."""
    response = requests.get(
        f"{API_URL}/alerts",
        params={"limit": 200},
        timeout=5,
    )
    response.raise_for_status()
    return response.json()


if st.button("Refresh alerts"):
    st.cache_data.clear()
    st.rerun()

try:
    alerts = fetch_alerts()

except requests.RequestException as exc:
    st.error(
        "Cannot connect to the safety API. "
        "Start the FastAPI backend and check its URL."
    )
    st.caption(f"Connection details: {exc}")
    st.stop()

if not alerts:
    st.info(
        "No alerts have been received yet. "
        "Run the simulator with the suspicious scenario to generate one."
    )
    st.stop()

df = pd.DataFrame(alerts)

# Ensure the fields expected by the dashboard are present.
required_columns = {
    "event_id",
    "device_id",
    "risk_level",
    "event_type",
    "received_at",
}

if not required_columns.issubset(df.columns):
    st.error("The API returned an unexpected alert format.")
    st.stop()

df["received_at"] = pd.to_datetime(
    df["received_at"],
    errors="coerce",
)

df["risk_level"] = df["risk_level"].str.upper()

total_alerts = len(df)
high_alerts = int((df["risk_level"] == "HIGH").sum())
medium_alerts = int((df["risk_level"] == "MEDIUM").sum())
low_alerts = int((df["risk_level"] == "LOW").sum())

st.subheader("Alert overview")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Recent alerts", total_alerts)
col2.metric("High risk", high_alerts)
col3.metric("Medium risk", medium_alerts)
col4.metric("Low risk", low_alerts)

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Alerts by risk level")

    risk_counts = (
        df["risk_level"]
        .value_counts()
        .reindex(["HIGH", "MEDIUM", "LOW"], fill_value=0)
    )

    st.bar_chart(risk_counts)

with right:
    st.subheader("Alerts by event type")

    event_counts = df["event_type"].value_counts()
    st.bar_chart(event_counts)

st.subheader("Recent alert history")

risk_filter = st.selectbox(
    "Filter by risk level",
    ["ALL", "HIGH", "MEDIUM", "LOW"],
)

filtered_df = df.copy()

if risk_filter != "ALL":
    filtered_df = filtered_df[
        filtered_df["risk_level"] == risk_filter
    ]

filtered_df = filtered_df.sort_values(
    "received_at",
    ascending=False,
    na_position="last",
)

st.dataframe(
    filtered_df[
        [
            "received_at",
            "event_id",
            "device_id",
            "risk_level",
            "event_type",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "The dashboard displays alert metadata returned by the API. "
    "Raw sensor readings are not stored in the alert table."
)
