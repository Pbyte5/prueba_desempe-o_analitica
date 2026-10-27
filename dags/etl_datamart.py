"""DAG for processing, transforming, loading, and validating the mall data mart."""

from datetime import timedelta
import pendulum
from airflow.sdk import Variable, dag, task

DATA_DIR = "/opt/airflow/data"
STAGING_DIR = "/opt/airflow/staging"
RULES_FILE = "/opt/airflow/seeds/category.csv"
CONN_ID = "datamart"

@dag(
    dag_id="datamart_mall_etl",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=1)}, 
    tags=["datamart", "etl"],
    doc_md=__doc__,
)
def etl():
    @task
    def extract_history_sales():
        from prueba_analitica.pipeline.scripts.extract import extract

        file_path = f"{DATA_DIR}/{Variable.get('datamart_history_files')}"
        return extract("history", file_path, STAGING_DIR)
    
    @task
    def extract_daily_sales():
        from prueba_analitica.pipeline.scripts.extract import extract

        file_path = f"{DATA_DIR}/{Variable.get('datamart_daily_files')}"
        return extract("daily", file_path, STAGING_DIR)
    
    @task
    def validate_and_transform(history, daily):
        from prueba_analitica.pipeline.scripts.transform import transform_staged
        
        priority = [v.strip() for v in Variable.get("datamart_source_priority").split(",")]
        return transform_staged(
            [history, daily],
            priority,
            Variable.get("datamart_source_tz"),
            RULES_FILE,
            STAGING_DIR,
            Variable.get("datamart_products_api_url"),
        )
    
    @task
    def load_to_db(processed):
        from prueba_analitica.pipeline.scripts.load import load
        

        load(processed["paths"], CONN_ID)
        
    @task 
    def run_quality_check(processed, loaded):
        from prueba_analitica.pipeline.scripts.data_quality import check_quality

        return check_quality(processed["stats"], CONN_ID)
    
    history = extract_history_sales()
    daily = extract_daily_sales()
    processed = validate_and_transform(history, daily)
    loaded = load_to_db(processed)
    run_quality_check(processed, loaded)
    
etl()