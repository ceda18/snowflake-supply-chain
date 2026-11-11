"""Chokepoint Monitor: Streamlit app on top of the GOLD layer.

Usage:
    streamlit run app/streamlit_app.py
"""
import pandas as pd
import snowflake.connector
import streamlit as st

st.set_page_config(page_title="Chokepoint Monitor", page_icon="🚢", layout="wide")

STATUS_ICON = {"DISRUPTED": "🔴 DISRUPTED", "SURGE": "🟠 SURGE", "NORMAL": "⚪️ NORMAL"}


@st.cache_resource
def get_conn():
    return snowflake.connector.connect(
        user="test",
        password="test",
        account="test",
        host="snowflake.localhost.localstack.cloud",
        port=4566,
        protocol="https",
        warehouse="COMPUTE_WH",
        database="SUPPLY_CHAIN",
        schema="GOLD",
    )


@st.cache_data(ttl=600)
def query(sql: str) -> pd.DataFrame:
    cur = get_conn().cursor()
    cur.execute(sql)
    df = pd.DataFrame(cur.fetchall(), columns=[d[0].lower() for d in cur.description])
    # Snowflake NUMBER arrives as Decimal; convert numeric columns, leave text and dates
    for col in df.columns:
        if df[col].dtype == "object":
            converted = pd.to_numeric(df[col], errors="coerce")
            if converted.notna().sum() == df[col].notna().sum():
                df[col] = converted
    return df


monitor = query("SELECT * FROM DISRUPTION_MONITOR ORDER BY change_pct")
rerouting = query("SELECT * FROM RED_SEA_REROUTING ORDER BY month")
weekly = query(
    "SELECT week_start, chokepoint_name, transits_total, transits_total_ly, yoy_pct "
    "FROM CHOKEPOINT_WEEKLY ORDER BY week_start"
)

as_of = pd.to_datetime(monitor["as_of_date"].iloc[0]).date() if not monitor.empty else "n/a"

# ---------------------------------------------------------------- header
st.title("🚢 Global Chokepoint Monitor")
st.caption(
    f"Daily shipment transits through {len(monitor)} global maritime chokepoints // "
    f"data as of {as_of} // source: IMF PortWatch"
)

# ---------------------------------------------------------------- KPIs
ranked = monitor.dropna(subset=["change_pct"])
c1, c2, c3 = st.columns(3)
if not ranked.empty:
    drop, surge = ranked.iloc[0], ranked.iloc[-1]
    c1.metric("% YoY Largest drop", drop["chokepoint_name"], f"{drop['change_pct']:.1f}% ships",
              help="Year over year data: current period compared to the same one last year.", delta_color = "blue")
    c2.metric("% YoY Largest increase", surge["chokepoint_name"], f"{surge['change_pct']:.1f}% ships",
              help="Year over year data: current period compared to the same one last year.", delta_color = "blue")
c3.metric("Disrupted chokepoints", f"# {int((monitor["status"] == "DISRUPTED").sum())}",
          help="Currently disrupted chockepoints in the database.")

st.divider()

# ---------------------------------------------------------------- disruption table
st.subheader("Disruption monitor")
st.caption("Average daily transits, last 30 days vs the same period one year earlier.")
table = monitor[["chokepoint_name", "avg_daily_last_30d", "avg_daily_same_30d_ly", "change_pct", "status"]].copy()
table["status"] = table["status"].map(STATUS_ICON)
st.dataframe(
    table,
    hide_index=True,
    use_container_width=True,
    column_config={
        "chokepoint_name": "Chokepoint",
        "avg_daily_last_30d": st.column_config.NumberColumn("# Transit/day, last 30d", format="%.1f"),
        "avg_daily_same_30d_ly": st.column_config.NumberColumn("# Transit/day, same period last year", format="%.1f"),
        "change_pct": st.column_config.NumberColumn("Change", format="%.1f%%"),
        "status": "Status",
    },
)

st.divider()

# ---------------------------------------------------------------- red sea rerouting
st.subheader("Red Sea rerouting")
st.caption(
    "Monthly transits. When attacks in the Red Sea escalated from late 2023, "
    "traffic shifted from the Suez Canal / Bab el-Mandeb route to the longer route around "
    "the Cape of Good Hope: longer voyages and tighter capacity on Asia-Europe lanes."
)
if not rerouting.empty:
    chart = rerouting.assign(month=pd.to_datetime(rerouting["month"])).set_index("month")[
        ["suez_canal", "bab_el_mandeb", "cape_of_good_hope"]
    ].rename(columns={
        "suez_canal": "Suez Canal",
        "bab_el_mandeb": "Bab el-Mandeb",
        "cape_of_good_hope": "Cape of Good Hope",
    })
    st.line_chart(chart)

st.divider()

# ---------------------------------------------------------------- explorer
st.subheader("Chokepoint explorer")
names = sorted(weekly["chokepoint_name"].unique())
default = names.index("Suez Canal") if "Suez Canal" in names else 0
selected = st.selectbox("Select chokepoint:", names, index=default)

sel = weekly[weekly["chokepoint_name"] == selected].copy()
sel["week_start"] = pd.to_datetime(sel["week_start"])
sel = sel[sel["week_start"] >= sel["week_start"].max() - pd.DateOffset(years=3)]

if not sel.empty:
    last = sel.iloc[-1]
    m1, m2 = st.columns(2)
    m1.metric("Transits, last full week", int(last["transits_total"]))
    if pd.notna(last["yoy_pct"]):
        m2.metric("Change compared compared to last year", f"{last['yoy_pct']:.1f}%")
    st.line_chart(
        sel.set_index("week_start")[["transits_total", "transits_total_ly"]].rename(
            columns={"transits_total": "This year", "transits_total_ly": "Same week last year"}
        )
    )

# st.divider()

# with st.expander("About this app"):
#     st.markdown(
#         "Developed by Čeda Veličković for practice reasons. "
#         "Source: IMF PortWatch"
#     )
