import json
import re

import streamlit as st

from smartpak_inventory.data import load_inventory_metrics
from smartpak_inventory.summaries import (
    build_verified_observations,
    generate_verified_sku_summary,
)


st.set_page_config(page_title="SmartPak Inventory & Metrics", layout="wide")
st.title("SmartPak Inventory & Metrics")
st.caption("Network inventory, trailing sales, and forward forecast")

INVENTORY_STATUS_VALUES = {
    "OOS": "OOS",
    "In stock": "IN STOCK",
    "No snapshot": "NO SNAPSHOT",
}


def reset_sku_filter():
    st.session_state["sku_filter"] = ""
    st.session_state.pop("sku_summary_result", None)
    st.session_state.pop("sku_summary_sku", None)


def reset_all_filters():
    st.session_state["category_filter"] = []
    st.session_state["supplier_filter"] = []
    st.session_state["planner_filter"] = []
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

filter_col_1, filter_col_2 = st.columns(2)
plymouth_status = filter_col_1.selectbox(
    "Plymouth inventory",
    ["All", *INVENTORY_STATUS_VALUES],
    key="plymouth_filter",
)
reno_status = filter_col_2.selectbox(
    "Reno inventory",
    ["All", *INVENTORY_STATUS_VALUES],
    key="reno_filter",
)

if plymouth_status != "All":
    inventory = inventory[
        inventory["PLYMOUTH_OOS"] == INVENTORY_STATUS_VALUES[plymouth_status]
    ]
if reno_status != "All":
    inventory = inventory[
        inventory["RENO_OOS"] == INVENTORY_STATUS_VALUES[reno_status]
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

metric_1, metric_2, metric_3, metric_4 = st.columns(4)
metric_1.metric("SKUs", f"{len(inventory):,}")
metric_2.metric("Network units on hand", f"{inventory['TOTAL_OH'].sum():,.0f}")
snapshot_inventory = inventory[
    inventory["INVENTORY_SNAPSHOT_STATUS"].eq("AVAILABLE")
]
metric_3.metric(
    "F30 network forecast/day",
    f"{snapshot_inventory['F30_AVG_DAILY_FORECAST'].sum():,.1f}",
)
metric_4.metric(
    "T30 network sales/day",
    f"{snapshot_inventory['T30_AVG_DAILY_SALES'].sum():,.1f}",
)
st.caption(
    "Forecast and sales/day summaries include only SKUs available in the "
    "latest inventory snapshot."
)

st.subheader("OOS SKUs by location")
selected_sku_count = len(inventory)
plymouth_oos_count = inventory["PLYMOUTH_OOS"].eq("OOS").sum()
reno_oos_count = inventory["RENO_OOS"].eq("OOS").sum()
no_snapshot_count = inventory["INVENTORY_SNAPSHOT_STATUS"].eq("NO SNAPSHOT").sum()

plymouth_oos_pct = (
    f"{plymouth_oos_count / selected_sku_count:.1%}" if selected_sku_count else "—"
)
reno_oos_pct = (
    f"{reno_oos_count / selected_sku_count:.1%}" if selected_sku_count else "—"
)

oos_metric_1, oos_metric_2, oos_metric_3, oos_metric_4 = st.columns(4)
oos_metric_1.metric("Plymouth OOS SKUs", f"{plymouth_oos_count:,}")
oos_metric_2.metric("Plymouth OOS %", plymouth_oos_pct)
oos_metric_3.metric("Reno OOS SKUs", f"{reno_oos_count:,}")
oos_metric_4.metric("Reno OOS %", reno_oos_pct)
st.caption(
    f"{no_snapshot_count:,} selected SKUs have no Plymouth/Reno record in the "
    "latest inventory snapshot and are not counted as OOS."
)

summary_inventory = inventory.copy()
summary_inventory.insert(0, "SKU_SUMMARY", False)

edited_inventory = st.data_editor(
    summary_inventory,
    column_config={
        "SKU_SUMMARY": st.column_config.CheckboxColumn(
            "SKU Summary",
            help="Select one SKU to prepare a Cortex-assisted summary.",
            default=False,
        ),
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
        "INVENTORY_SNAPSHOT_STATUS": "Inventory snapshot status",
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
    disabled=inventory.columns.tolist(),
    hide_index=True,
    use_container_width=True,
    key="inventory_summary_editor",
)

selected_summary_rows = edited_inventory[edited_inventory["SKU_SUMMARY"]]
if len(selected_summary_rows) > 1:
    st.warning("Select only one SKU at a time to generate a summary.")
elif len(selected_summary_rows) == 1:
    selected_row = selected_summary_rows.iloc[0]
    selected_sku = str(selected_row["SKU_NUMBER"]).strip()

    if st.session_state.get("sku_summary_sku") != selected_sku:
        st.session_state.pop("sku_summary_result", None)

    if st.button("Generate SKU summary", type="primary"):
        verified_observations = build_verified_observations(selected_row)
        observations_json = json.dumps(
            verified_observations,
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            with st.spinner(f"Reviewing SKU {selected_sku} with Cortex…"):
                st.session_state["sku_summary_result"] = (
                    generate_verified_sku_summary(selected_sku, observations_json)
                )
                st.session_state["sku_summary_sku"] = selected_sku
        except Exception as exc:
            st.error(
                "The SKU summary could not be generated. Confirm that the app "
                "role has access to Snowflake Cortex AI functions."
            )
            with st.expander("Technical details"):
                st.exception(exc)

    summary_result = st.session_state.get("sku_summary_result")
    if summary_result and summary_result.get("sku_number") == selected_sku:
        st.subheader(f"Executive SKU summary for {selected_sku}")
        st.caption(
            "Cortex prioritizes verified observations calculated by the app; "
            "it cannot add new numbers or unsupported explanations."
        )
        st.write(" ".join(summary_result["observations"]))
        st.info(
            "A material variance means 25% or more. On-order inventory is not "
            "included. T30/T90/T180 and F30/F90/F180 compare rolling averages "
            "across horizons; they do not measure day-to-day volatility."
        )

st.subheader("Source of truth guide")
st.caption(
    "Raw warehouse fields used by this dashboard are listed below. Calculated "
    "and derived dashboard columns are omitted."
)

source_of_truth = [
    {
        "Data source": "SMARTPAK_PRD.CORE.DIMPRODUCTSKU",
        "Column headers": (
            "SKUID, SKUNAME, PRODUCTSKUKEY, PRODUCTCATEGORY, SUPPLIERNAME, "
            "LEADTIMEMONTHS, CONTROLBUYERNAME, ROWCURRENTFLAG, "
            "SKUINACTIVEFLAG, PRODUCTINACTIVEFLAG"
        ),
    },
    {
        "Data source": "SMARTPAK_PRD.DBO.TBLSTOCKRECORDSNAPSHOT",
        "Column headers": "PRODUCTID, ACTUALSTOCK, FACILITYNAME, ENDOFWEEKDATE",
    },
    {
        "Data source": "SMARTPAK_PRD.SALES.FACTSALESDETAIL",
        "Column headers": (
            "PRODUCTSKUKEY, ORDERDATEKEY, ORDEREDQUANTITY, DEMANDFLAG"
        ),
    },
    {
        "Data source": (
            "EDLDB.SC_SANDBOX."
            "BEZOS_PROD_FCST_ITEM_DAY_NETWORK_COLT_SMARTEQUINE"
        ),
        "Column headers": (
            "PRODUCT_PART_NUMBER, FCST_QTY, SNAPSHOT_DATE, FORECAST_DATE"
        ),
    },
]

st.dataframe(
    source_of_truth,
    column_config={
        "Data source": st.column_config.TextColumn("Data source", width="large"),
        "Column headers": st.column_config.TextColumn(
            "Column headers pulled from that data source",
            width="large",
        ),
    },
    hide_index=True,
    use_container_width=True,
)
