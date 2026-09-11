# SmartPak-Inventory-Metrics
Project for creating the data sources related to SmartPak. 
This repo will grow as the business evolves and data merges from temporary snowflake tables to permanent Chewy data sources. 

## First dashboard slice

The initial Streamlit page shows network, Plymouth, and Reno on-hand inventory,
plus average daily trailing sales and forward forecast over 30, 90, and 180
days. It also calculates days of supply and lead-time risk for each horizon.

1. Create and activate a Python virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and fill
   in your Snowflake connection values. Never commit `secrets.toml`.
4. Run `streamlit run streamlit_app.py`.

Forecast windows use an inclusive start and exclusive end, so the 30-day
average contains exactly 30 forecast dates and the 180-day average exactly 180.

## Deploy to Streamlit in Snowflake

The app automatically uses Snowflake's managed Snowpark session when deployed.
No username or password is stored in the hosted app. The local secrets file is
only a fallback for development outside Snowflake.

1. Push the application files to the GitHub branch used for deployment.
2. In Snowsight, create or open a Git-backed workspace for this repository.
3. Select `streamlit_app.py` as the app entry point.
4. Deploy the workspace to an approved database, schema, query warehouse, and
   compute pool.
5. Share the deployed Streamlit object with the appropriate viewer role.

`environment.yml` defines the Python 3.11 warehouse-runtime dependencies. A
`snowflake.yml` can be added later if deployment is automated with Snowflake
CLI; it requires the final app object and warehouse names.
