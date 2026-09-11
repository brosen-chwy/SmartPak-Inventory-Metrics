import re

import streamlit as st

from smartpak_inventory.data import load_inventory_metrics


st.set_page_config(page_title="SmartPak Inventory & Metrics", layout="wide")
st.title("SmartPak Inventory & Metrics")
st.caption("Network inventory, trailing sales, and forward forecast")

RISK_COLUMNS = {
    "T30": "T30_LT_RISK",
    "T90": "T90_LT_RISK",
    "T180": "T180_LT_RISK",
    "F30": "F30_LT_RISK",
    "F90": "F90_LT_RISK",
    "F180": "F180_LT_RISK",
}


def reset_sku_filter():
    st.session_state["sku_filter"] = ""


def reset_all_filters():
    st.session_state["category_filter"] = []
    st.session_state["supplier_filter"] = []
    st.session_state["planner_filter"] = []
    st.session_state["risk_filter"] = []
    st.session_state["plymouth_filter"] = "All"
    st.session_state["reno_filter"] = "All"
    reset_sku_filter()


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

category_options = sorted(inventory["PRODUCT_CATEGORY"].dropna().unique().tolist())
supplier_options = sorted(inventory["SUPPLIER_NAME"].dropna().unique().tolist())
planner_options = sorted(inventory["SUPPLY_PLANNER"].dropna().unique().tolist())

category_col, supplier_col, planner_col = st.columns(3)
selected_categories = category_col.multiselect(
    "Product category",
    category_options,
    placeholder="All product categories",
    key="category_filter",
)
selected_suppliers = supplier_col.multiselect(
    "Supplier",
    supplier_options,
    placeholder="All suppliers",
    key="supplier_filter",
)
selected_planners = planner_col.multiselect(
    "Supply planner",
    planner_options,
    placeholder="All supply planners",
    key="planner_filter",
)

if selected_categories:
    inventory = inventory[inventory["PRODUCT_CATEGORY"].isin(selected_categories)]
if selected_suppliers:
    inventory = inventory[inventory["SUPPLIER_NAME"].isin(selected_suppliers)]
if selected_planners:
    inventory = inventory[inventory["SUPPLY_PLANNER"].isin(selected_planners)]

filter_col_1, filter_col_2, filter_col_3 = st.columns([2, 1, 1])
selected_risks = filter_col_1.multiselect(
    "At-risk horizon",
    list(RISK_COLUMNS),
    placeholder="All risk statuses",
    help="When multiple horizons are selected, a SKU is shown only if it is at risk in every selected horizon.",
    key="risk_filter",
)
plymouth_status = filter_col_2.selectbox(
    "Plymouth inventory",
    ["All", "OOS", "In stock"],
    key="plymouth_filter",
)
reno_status = filter_col_3.selectbox(
    "Reno inventory",
    ["All", "OOS", "In stock"],
    key="reno_filter",
)

if selected_risks:
    risk_mask = inventory[
        [RISK_COLUMNS[horizon] for horizon in selected_risks]
    ].eq("AT RISK").all(axis=1)
    inventory = inventory[risk_mask]
if plymouth_status != "All":
    inventory = inventory[
        inventory["PLYMOUTH_OOS"] == ("OOS" if plymouth_status == "OOS" else "IN STOCK")
    ]
if reno_status != "All":
    inventory = inventory[
        inventory["RENO_OOS"] == ("OOS" if reno_status == "OOS" else "IN STOCK")
    ]

sku_search = st.text_area(
    "Filter by SKU(s)",
    placeholder="Paste one or more SKUs separated by commas, spaces, tabs, or new lines",
    height=100,
    key="sku_filter",
)
reset_sku_col, reset_all_col, _ = st.columns([1, 1, 4])
reset_sku_col.button("Reset SKU filter", on_click=reset_sku_filter)
reset_all_col.button("Reset all filters", on_click=reset_all_filters)

if sku_search:
    sku_values = [
        value for value in re.split(r"[\s,;|]+", sku_search.strip()) if value
    ]
    sku_numbers = inventory["SKU_NUMBER"].astype(str).str.strip()
    if len(sku_values) == 1:
        sku_mask = sku_numbers.str.contains(
            sku_values[0], case=False, na=False, regex=False
        )
    else:
        normalized_skus = {value.upper() for value in sku_values}
        sku_mask = sku_numbers.str.upper().isin(normalized_skus)
    inventory = inventory[sku_mask]

metric_1, metric_2 = st.columns(2)
metric_1.metric("SKUs", f"{len(inventory):,}")
metric_2.metric("Network units on hand", f"{inventory['TOTAL_OH'].sum():,.0f}")

st.subheader("SKUs at risk by horizon - Network Level")
st.caption("On-order inventory is not currently included in these risk calculations.")
risk_metrics = st.columns(6)
for metric, (label, column) in zip(risk_metrics, RISK_COLUMNS.items()):
    metric.metric(label, f"{inventory[column].eq('AT RISK').sum():,}")

st.subheader("OOS SKUs by location")
oos_metric_1, oos_metric_2 = st.columns(2)
oos_metric_1.metric(
    "Plymouth OOS SKUs", f"{inventory['PLYMOUTH_OOS'].eq('OOS').sum():,}"
)
oos_metric_2.metric("Reno OOS SKUs", f"{inventory['RENO_OOS'].eq('OOS').sum():,}")

st.dataframe(
    inventory,
    column_config={
        "SKU_NUMBER": "SKU",
        "SKU_NAME": "SKU name",
        "PRODUCT_CATEGORY": "Product category",
        "SUPPLIER_NAME": "Supplier",
        "SUPPLY_PLANNER": "Supply planner",
        "LEAD_TIME_MONTHS": "Lead time (months)",
        "LEAD_TIME_DAYS": "Lead time (days)",
        "TOTAL_OH": st.column_config.NumberColumn("Network OH", format="%.0f"),
        "PLYMOUTH_OH": st.column_config.NumberColumn("Plymouth OH", format="%.0f"),
        "RENO_OH": st.column_config.NumberColumn("Reno OH", format="%.0f"),
        "PLYMOUTH_OOS": "Plymouth status",
        "RENO_OOS": "Reno status",
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
