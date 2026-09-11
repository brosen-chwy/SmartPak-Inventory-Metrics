import streamlit as st

from smartpak_inventory.data import load_inventory_metrics


st.set_page_config(page_title="SmartPak Inventory & Metrics", layout="wide")
st.title("SmartPak Inventory & Metrics")
st.caption("Network inventory, trailing sales, and forward forecast")

try:
    inventory = load_inventory_metrics()
except Exception as exc:
    st.error(
        "Inventory data could not be loaded. Run the app in Snowflake or check "
        "your local Snowflake connection settings."
    )
    with st.expander("Technical details"):
        st.exception(exc)
    st.stop()

search = st.text_input("Filter by SKU", placeholder="Enter all or part of a SKU")
if search:
    inventory = inventory[
        inventory["SKU_NUMBER"].astype(str).str.contains(search, case=False, na=False)
    ]

metric_1, metric_2 = st.columns(2)
metric_1.metric("SKUs", f"{len(inventory):,}")
metric_2.metric("Network units on hand", f"{inventory['TOTAL_OH'].sum():,.0f}")

st.dataframe(
    inventory,
    column_config={
        "SKU_NUMBER": "SKU",
        "SKU_NAME": "SKU name",
        "PRODUCT_CATEGORY": "Product category",
        "SUPPLY_PLANNER": "Supply planner",
        "LEAD_TIME_MONTHS": "Lead time (months)",
        "LEAD_TIME_DAYS": "Lead time (days)",
        "TOTAL_OH": st.column_config.NumberColumn("Network OH", format="%.0f"),
        "PLYMOUTH_OH": st.column_config.NumberColumn("Plymouth OH", format="%.0f"),
        "RENO_OH": st.column_config.NumberColumn("Reno OH", format="%.0f"),
        "T30_AVG_DAILY_SALES": st.column_config.NumberColumn("T30 avg sales", format="%.2f"),
        "T30_DOS": st.column_config.NumberColumn("T30 DOS", format="%.1f"),
        "T90_AVG_DAILY_SALES": st.column_config.NumberColumn("T90 avg sales", format="%.2f"),
        "T90_DOS": st.column_config.NumberColumn("T90 DOS", format="%.1f"),
        "T180_AVG_DAILY_SALES": st.column_config.NumberColumn("T180 avg sales", format="%.2f"),
        "T180_DOS": st.column_config.NumberColumn("T180 DOS", format="%.1f"),
        "F30_AVG_DAILY_FORECAST": st.column_config.NumberColumn("F30 avg forecast", format="%.2f"),
        "F30_DOS": st.column_config.NumberColumn("F30 DOS", format="%.1f"),
        "F90_AVG_DAILY_FORECAST": st.column_config.NumberColumn("F90 avg forecast", format="%.2f"),
        "F90_DOS": st.column_config.NumberColumn("F90 DOS", format="%.1f"),
        "F180_AVG_DAILY_FORECAST": st.column_config.NumberColumn("F180 avg forecast", format="%.2f"),
        "F180_DOS": st.column_config.NumberColumn("F180 DOS", format="%.1f"),
    },
    hide_index=True,
    use_container_width=True,
)
