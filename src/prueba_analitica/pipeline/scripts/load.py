"""Load: loads clean parquet datasets into PostgreSQL using bulk COPY operations and updates aggregations."""

import io

import pandas as pd
from airflow.providers.postgres.hooks.postgres import PostgresHook

TRUNCATE_ALL = """
TRUNCATE fact_daily_product, fact_returns, fact_sales, rejected_records, dim_product RESTART IDENTITY
"""

BUILD_DAILY = """
INSERT INTO fact_daily_product
    (invoice_date, stock_code, units_sold, units_returned, gross_revenue, returns_amount, net_revenue)
WITH sold AS (
    SELECT invoice_date, stock_code, SUM(quantity) AS units, SUM(gross_revenue) AS amount
    FROM fact_sales GROUP BY invoice_date, stock_code
), returned AS (
    SELECT invoice_date, stock_code, SUM(quantity_returned) AS units, SUM(return_amount) AS amount
    FROM fact_returns GROUP BY invoice_date, stock_code
)
SELECT invoice_date, stock_code,
       COALESCE(sold.units, 0), COALESCE(returned.units, 0),
       COALESCE(sold.amount, 0), COALESCE(returned.amount, 0),
       COALESCE(sold.amount, 0) - COALESCE(returned.amount, 0)
FROM sold FULL OUTER JOIN returned USING (invoice_date, stock_code)
"""

COLUMNS = {
    "dim_product": ["stock_code", "description", "category", "category_source",
                    "n_raw_description_variants", "n_description_variants",
                    "has_inconsistent_description", "first_seen_date", "last_seen_date"],
    "fact_sales": ["invoice_no", "stock_code", "customer_id", "is_guest", "country", "invoice_ts_utc",
                   "invoice_date", "quantity", "unit_price", "gross_revenue", "source"],
    "fact_returns": ["invoice_no", "stock_code", "customer_id", "is_guest", "country", "invoice_ts_utc",
                     "invoice_date", "quantity_returned", "unit_price", "return_amount", "movement_type", "source"],
    "rejected_records": ["source", "source_row", "reason", "invoice_no", "stock_code", "description",
                         "quantity", "unit_price", "invoice_date_raw", "customer_id", "country"],
}
FILES = {"dim_product": "products", "fact_sales": "sales", "fact_returns": "returns", "rejected_records": "rejected"}


def copy_into(cursor, table, df):
    """Executes a bulk PostgreSQL COPY operation from a pandas DataFrame via an in-memory buffer."""
    columns = COLUMNS[table]
    buffer = io.StringIO()
    df[columns].to_csv(buffer, index=False, header=False)
    buffer.seek(0)
    sql = f"COPY {table} ({', '.join(columns)}) FROM STDIN WITH (FORMAT csv)"
    if hasattr(cursor, "copy_expert"):  
        cursor.copy_expert(sql, buffer)
    else:  
        with cursor.copy(sql) as copy:
            while chunk := buffer.read(1 << 20):  
                copy.write(chunk.encode("utf-8"))


def load(paths, conn_id):
    """Load task: reads clean parquet files, truncates target tables, bulk loads data into PostgreSQL, and builds daily aggregates."""
    connection = PostgresHook(postgres_conn_id=conn_id).get_conn()
    try:
        with connection.cursor() as cursor:
            cursor.execute(TRUNCATE_ALL)
            for table in ["dim_product", "fact_sales", "fact_returns", "rejected_records"]:
                copy_into(cursor, table, pd.read_parquet(paths[FILES[table]]))
            cursor.execute(BUILD_DAILY)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()