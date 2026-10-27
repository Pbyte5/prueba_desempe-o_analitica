"""Extraction: reads a raw CSV, unifies column names, and saves it to the staging area"""

import pandas as pd 
import re
import logging
from pathlib import Path

#Good practices, says where the log is coming from
log = logging.getLogger(__name__)

#Names Normalization of both datasets
COLUMN_NAMES = {
    "invoice_no"       : ["invoiceno", "invoice"],
    "stock_code"       : ["stockcode"],
    "description"      : ["description"],
    "quantity"         : ["quantity"],
    "invoice_date_raw" : ["invoicedate"],
    "unit_price"       : ["unitprice", "price"],
    "customer_id"      : ["customerid"],
    "country"          : ["country"]
}




def unified_name(column):
    """
    Normalizes a given column name by removing special characters and spaces, 
    then matches it against the standard column dictionary. 
    """
    
    key = re.sub(r"[^a-z0-9]", "", column.lower())
    for name, options in COLUMN_NAMES.items():
        if key in options:
            return name
    return None


def read_csv(path, source):
    """
    Reads the entire CSV as text (without inferring data types) and standardizes the column names.
    """
    
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} Doesn't exists. Copy all the files in data/raw/ (Or read README).")
    
    #Na settings 
    options = {"dtype" : str, "keep_default_na" : False, "na_values" :[""]}
    try:
        df = pd.read_csv(path, encoding="utf-8", **options)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="latin-1", **options)
        
    #Check Columns
    df = df.rename(columns={ c:unified_name(c) for c in df.columns if unified_name(c)})
    missing = set(COLUMN_NAMES) - set(df.columns)
    if missing:
        raise ValueError(f"{path.name}: Some columns are missing! {sorted(missing)}; Found: {list(df.columns)}")
    
    df = df[list(COLUMN_NAMES)]
    df.insert(0, "source_row", range(len(df)))
    df.insert(0, "source", source)
    return df




def log_profile(df, source):
    """
    Performs a quick data exploration of the source. 
    Outputs to the task log (serves as evidence for the decision-making document).
    """
    
    quantity = pd.to_numeric(df["quantity"], errors="coerce")
    price = pd.to_numeric(df["unit_price"], errors="coerce")
    codes = (
        df["stock_code"]
        .str.strip()
        .str.upper()
        .str.replace(r"\s+", "", regex=True)
    )
    
    log.info("[%s] Rows: %d | columns: %s", source, len(df), list(df.columns[2:]))
    log.info("[%s] Null per columns: %s", source, df.iloc[:, 2:].isna().sum().to_dict())
    log.info("[%s] Quantities <= 0: %d | precio <= 0: %d", source, (quantity <= 0).sum(), (price <= 0).sum())
    log.info("[%s] Duplicated Rows: %d", source, df.duplicated(subset=list(df.columns[2:])).sum())
    log.info("[%s] Products with differents codes: %d | Distincs descriptions: %d", source, codes.nunique(), df["description"].nunique())
    
def extract(source, path,staging_dir):
    """
    Extraction task: converts a raw CSV to a Parquet file in the staging directory. 
    Returns lightweight metadata (intended to be passed via Airflow XComs).
    """
    df = read_csv(path=path, source= source)
    log_profile(df,source)
    
    out = Path(staging_dir) / f"raw_{source}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index= False)
    return {"source" : source, "path" : str(out), "rows" : len(df)}