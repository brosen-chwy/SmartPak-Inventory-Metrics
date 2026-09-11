from typing import Optional

import pandas as pd
import streamlit as st

from smartpak_inventory.queries import INVENTORY_METRICS_SQL


def _load_from_snowflake_runtime() -> Optional[pd.DataFrame]:
    """Use the managed session when running as a Streamlit in Snowflake app."""
    try:
        from snowflake.snowpark.context import get_active_session

        session = get_active_session()
    except Exception:
        return None

    return session.sql(INVENTORY_METRICS_SQL).to_pandas()


def _load_from_local_connection() -> pd.DataFrame:
    """Use local Streamlit secrets when developing outside Snowflake."""
    import snowflake.connector

    connection = snowflake.connector.connect(**dict(st.secrets["snowflake"]))
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(INVENTORY_METRICS_SQL)
            return cursor.fetch_pandas_all()
        finally:
            cursor.close()
    finally:
        connection.close()


@st.cache_data(ttl=60 * 60, show_spinner="Loading inventory metrics from Snowflake…")
def load_inventory_metrics() -> pd.DataFrame:
    """Return inventory, trailing sales, and forecast metrics by SKU."""
    hosted_result = _load_from_snowflake_runtime()
    if hosted_result is not None:
        return hosted_result

    return _load_from_local_connection()
