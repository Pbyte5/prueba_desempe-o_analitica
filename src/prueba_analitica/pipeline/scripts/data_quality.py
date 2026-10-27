"""Data Quality: validates loaded data against staging statistics and financial integrity constraints in PostgreSQL."""

import pandas as pd
from airflow.providers.postgres.hooks.postgres import PostgresHook


def check_quality(stats, connection_id):
    """
    Validates data quality after loading into PostgreSQL by comparing row counts,
    aggregates, and financial integrity constraints against expected staging statistics.
    """
    hook = PostgresHook(postgres_conn_id=connection_id)
    
    def scalar(sql):
        return hook.get_first(sql)[0]
    
    db = {
        "sales": scalar("SELECT COUNT(*) FROM fact_sales"),
        "returns": scalar("SELECT COUNT(*) FROM fact_returns"),
        "rejected": scalar("SELECT COUNT(*) FROM rejected_records"),
        "products": scalar("SELECT COUNT(*) FROM dim_product"),
    }
    
    expected = {
        "sales": stats["sales_rows"], 
        "returns": stats["returns_rows"],
        "rejected": stats["rejected_rows"], 
        "products": stats["products"]
    }

    problems = [
        f"{name}: expected {expected[name]}, loaded {db[name]}"
        for name in expected if db[name] != expected[name]
    ]
    
    loaded = db["sales"] + db["returns"] + db["rejected"]
    if loaded != stats["rows_in"]:
        problems.append(f"Total rows {stats['rows_in']} != sales + returns + rejected ({loaded})")
        
    if scalar("SELECT COALESCE(SUM(gross_revenue), 0) FROM fact_sales") != \
        scalar("SELECT COALESCE(SUM(gross_revenue), 0) FROM fact_daily_product"):
        problems.append("Gross revenue in fact_daily_product does not match fact_sales")
        
    if scalar("SELECT COALESCE(SUM(return_amount), 0) FROM fact_returns") != \
        scalar("SELECT COALESCE(SUM(returns_amount), 0) FROM fact_daily_product"):
        problems.append("Returns amount in fact_daily_product does not match fact_returns")
        
    if scalar("SELECT COUNT(*) FROM fact_daily_product WHERE net_revenue <> gross_revenue - returns_amount"):
        problems.append("There are rows where net_revenue != gross_revenue - returns_amount")

    if problems:
        raise ValueError("Quality check failed: " + "; ".join(problems))
        
    return {"status": "ok", **db}