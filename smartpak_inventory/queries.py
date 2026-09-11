INVENTORY_METRICS_SQL = """
WITH product_backbone AS (
    SELECT
        p.SKUID,
        p.SKUNAME,
        p.PRODUCTSKUKEY,
        p.PRODUCTCATEGORY,
        p.SUPPLIERNAME,
        p.LEADTIMEMONTHS,
        ROUND(p.LEADTIMEMONTHS * 30, 0) AS LEADTIMEDAYS,
        p.CONTROLBUYERNAME
    FROM SMARTPAK_PRD.CORE.DIMPRODUCTSKU p
    WHERE p.ROWCURRENTFLAG = TRUE
      AND p.SKUINACTIVEFLAG = FALSE
      AND p.PRODUCTINACTIVEFLAG = FALSE
      AND p.PRODUCTCATEGORY NOT IN (
          'Cardboard - SS', 'Cardboard - SP', 'Cardboard - 50/50',
          'Cardboard - 75/25', 'Misc. Packaging', 'Kraft Paper', 'Gum Tape'
      )
),

inventory AS (
    SELECT
        s.PRODUCTID AS SKUID,
        SUM(s.ACTUALSTOCK) AS total_oh,
        SUM(CASE WHEN s.FACILITYNAME = 'Plymouth' THEN s.ACTUALSTOCK ELSE 0 END)
            AS plymouth_oh,
        SUM(CASE WHEN s.FACILITYNAME = 'Reno' THEN s.ACTUALSTOCK ELSE 0 END)
            AS reno_oh
    FROM SMARTPAK_PRD.DBO.TBLSTOCKRECORDSNAPSHOT s
    WHERE s.ENDOFWEEKDATE = (
        SELECT MAX(ENDOFWEEKDATE)
        FROM SMARTPAK_PRD.DBO.TBLSTOCKRECORDSNAPSHOT
    )
      AND s.FACILITYNAME IN ('Plymouth', 'Reno')
    GROUP BY s.PRODUCTID
),

trailing_sales AS (
    SELECT
        sd.PRODUCTSKUKEY,
        SUM(CASE
                WHEN sd.ORDERDATEKEY >= TO_NUMBER(
                    TO_CHAR(DATEADD('day', -30, CURRENT_DATE), 'YYYYMMDD')
                ) THEN sd.ORDEREDQUANTITY
                ELSE 0
            END) / 30.0 AS t30_avg_daily_sales,
        SUM(CASE
                WHEN sd.ORDERDATEKEY >= TO_NUMBER(
                    TO_CHAR(DATEADD('day', -90, CURRENT_DATE), 'YYYYMMDD')
                ) THEN sd.ORDEREDQUANTITY
                ELSE 0
            END) / 90.0 AS t90_avg_daily_sales,
        SUM(sd.ORDEREDQUANTITY) / 180.0 AS t180_avg_daily_sales
    FROM SMARTPAK_PRD.SALES.FACTSALESDETAIL sd
    WHERE sd.ORDERDATEKEY >= TO_NUMBER(
              TO_CHAR(DATEADD('day', -180, CURRENT_DATE), 'YYYYMMDD')
          )
      AND sd.ORDERDATEKEY < TO_NUMBER(TO_CHAR(CURRENT_DATE, 'YYYYMMDD'))
      AND sd.DEMANDFLAG = TRUE
    GROUP BY sd.PRODUCTSKUKEY
),

forward_forecast AS (
    SELECT
        PRODUCT_PART_NUMBER AS skuid,
        SUM(CASE
                WHEN FORECAST_DATE < DATEADD('day', 30, CURRENT_DATE)
                THEN FCST_QTY ELSE 0
            END) / 30.0 AS f30_avg_daily_forecast,
        SUM(CASE
                WHEN FORECAST_DATE < DATEADD('day', 90, CURRENT_DATE)
                THEN FCST_QTY ELSE 0
            END) / 90.0 AS f90_avg_daily_forecast,
        SUM(FCST_QTY) / 180.0 AS f180_avg_daily_forecast
    FROM EDLDB.SC_SANDBOX.BEZOS_PROD_FCST_ITEM_DAY_NETWORK_COLT_SMARTEQUINE
    WHERE SNAPSHOT_DATE = CURRENT_DATE
      AND FORECAST_DATE >= CURRENT_DATE
      AND FORECAST_DATE < DATEADD('day', 180, CURRENT_DATE)
    GROUP BY PRODUCT_PART_NUMBER
),

metrics AS (
    SELECT
        p.*,
        i.total_oh,
        i.plymouth_oh,
        i.reno_oh,
        IFF(i.SKUID IS NULL, 'NO SNAPSHOT', 'AVAILABLE')
            AS inventory_snapshot_status,
        ts.t30_avg_daily_sales,
        ts.t90_avg_daily_sales,
        ts.t180_avg_daily_sales,
        ff.f30_avg_daily_forecast,
        ff.f90_avg_daily_forecast,
        ff.f180_avg_daily_forecast
    FROM product_backbone p
    LEFT JOIN inventory i ON p.SKUID = i.SKUID
    LEFT JOIN trailing_sales ts ON p.PRODUCTSKUKEY = ts.PRODUCTSKUKEY
    LEFT JOIN forward_forecast ff ON CAST(p.SKUID AS TEXT) = ff.skuid
)

SELECT
    SKUID AS sku_number,
    SKUNAME AS sku_name,
    PRODUCTCATEGORY AS product_category,
    SUPPLIERNAME AS supplier_name,
    CONTROLBUYERNAME AS supply_planner,
    LEADTIMEMONTHS AS lead_time_months,
    LEADTIMEDAYS AS lead_time_days,
    total_oh,
    plymouth_oh,
    reno_oh,
    CASE
        WHEN inventory_snapshot_status = 'NO SNAPSHOT' THEN 'NO SNAPSHOT'
        WHEN plymouth_oh <= 0 THEN 'OOS'
        ELSE 'IN STOCK'
    END AS plymouth_oos,
    CASE
        WHEN inventory_snapshot_status = 'NO SNAPSHOT' THEN 'NO SNAPSHOT'
        WHEN reno_oh <= 0 THEN 'OOS'
        ELSE 'IN STOCK'
    END AS reno_oos,
    inventory_snapshot_status,
    ROUND(t30_avg_daily_sales, 2) AS t30_avg_daily_sales,
    ROUND(DIV0(total_oh, t30_avg_daily_sales), 1) AS t30_dos,
    ROUND(t90_avg_daily_sales, 2) AS t90_avg_daily_sales,
    ROUND(DIV0(total_oh, t90_avg_daily_sales), 1) AS t90_dos,
    ROUND(t180_avg_daily_sales, 2) AS t180_avg_daily_sales,
    ROUND(DIV0(total_oh, t180_avg_daily_sales), 1) AS t180_dos,
    ROUND(f30_avg_daily_forecast, 2) AS f30_avg_daily_forecast,
    ROUND(DIV0(total_oh, f30_avg_daily_forecast), 1) AS f30_dos,
    ROUND(f90_avg_daily_forecast, 2) AS f90_avg_daily_forecast,
    ROUND(DIV0(total_oh, f90_avg_daily_forecast), 1) AS f90_dos,
    ROUND(f180_avg_daily_forecast, 2) AS f180_avg_daily_forecast,
    ROUND(DIV0(total_oh, f180_avg_daily_forecast), 1) AS f180_dos,
    CASE
        WHEN inventory_snapshot_status = 'NO SNAPSHOT' THEN 'NO SNAPSHOT'
        WHEN t30_avg_daily_sales > 0
         AND DIV0(total_oh, t30_avg_daily_sales) <= LEADTIMEDAYS THEN 'AT RISK'
        ELSE 'OK'
    END AS t30_lt_risk,
    CASE
        WHEN inventory_snapshot_status = 'NO SNAPSHOT' THEN 'NO SNAPSHOT'
        WHEN t90_avg_daily_sales > 0
         AND DIV0(total_oh, t90_avg_daily_sales) <= LEADTIMEDAYS THEN 'AT RISK'
        ELSE 'OK'
    END AS t90_lt_risk,
    CASE
        WHEN inventory_snapshot_status = 'NO SNAPSHOT' THEN 'NO SNAPSHOT'
        WHEN t180_avg_daily_sales > 0
         AND DIV0(total_oh, t180_avg_daily_sales) <= LEADTIMEDAYS THEN 'AT RISK'
        ELSE 'OK'
    END AS t180_lt_risk,
    CASE
        WHEN inventory_snapshot_status = 'NO SNAPSHOT' THEN 'NO SNAPSHOT'
        WHEN f30_avg_daily_forecast > 0
         AND DIV0(total_oh, f30_avg_daily_forecast) <= LEADTIMEDAYS THEN 'AT RISK'
        ELSE 'OK'
    END AS f30_lt_risk,
    CASE
        WHEN inventory_snapshot_status = 'NO SNAPSHOT' THEN 'NO SNAPSHOT'
        WHEN f90_avg_daily_forecast > 0
         AND DIV0(total_oh, f90_avg_daily_forecast) <= LEADTIMEDAYS THEN 'AT RISK'
        ELSE 'OK'
    END AS f90_lt_risk,
    CASE
        WHEN inventory_snapshot_status = 'NO SNAPSHOT' THEN 'NO SNAPSHOT'
        WHEN f180_avg_daily_forecast > 0
         AND DIV0(total_oh, f180_avg_daily_forecast) <= LEADTIMEDAYS THEN 'AT RISK'
        ELSE 'OK'
    END AS f180_lt_risk
FROM metrics
ORDER BY total_oh DESC NULLS LAST
"""
