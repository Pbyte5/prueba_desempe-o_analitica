"""Transformation: cleans, standardizes, validates, and transforms raw parquet datasets into clean analytics-ready datasets."""

import re 
from pathlib import Path

import numpy as np
import pandas as pd


### Business rules

# Real product: 5 digits + 0 to 2 letters
CATALOG_CODE = r"^\d{5}[A-Z]{0,2}$"

# Date formats accepted for parsing
DATE_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S"]
COUNTRY_FORMATS = {"EIRE": "Ireland", "RSA": "South Africa", "USA": "United States"}
DEFAULT_CATEGORY = "Hogar"
DUPLICATE_KEY = ["invoice_no", "stock_code", "quantity", "unit_price", "invoice_ts_utc", "customer_id"]
REJECT_COLUMNS = [
    "source", 
    "source_row", 
    "reason", 
    "invoice_no", 
    "stock_code", 
    "description",
    "quantity", 
    "unit_price", 
    "invoice_date_raw", 
    "customer_id", 
    "country"
]


def clean_text(texts):
    """Strips whitespace, collapses multiple internal spaces, and masks empty strings as NA."""
    text = (
        texts.astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )
    return text.mask(text == "")


def parse_dates(series):
    """Attempts to parse a series of date strings using multiple predefined formats."""
    result = pd.to_datetime(series, format=DATE_FORMATS[0], errors="coerce")
    for date_format in DATE_FORMATS[1:]:
        result = result.fillna(pd.to_datetime(series, format=date_format, errors="coerce"))
    return result


def to_utc(local_times, timezone):
    """Localizes timestamps to a given timezone and converts them to UTC."""
    ambiguous = np.zeros(len(local_times), dtype=bool)
    local = local_times.dt.tz_localize(timezone, ambiguous=ambiguous, nonexistent="shift_forward")
    return local.dt.tz_convert("UTC")


def standardize(raw, timezone):
    """Standardizes raw columns, applies data types, computes UTC timestamps, and normalizes country names."""
    df = pd.DataFrame(index=raw.index)
    df["source"] = raw["source"]
    df["source_row"] = raw["source_row"]
    df["invoice_no"] = clean_text(raw["invoice_no"]).str.upper()
    df["stock_code"] = clean_text(raw["stock_code"]).str.replace(" ", "").str.upper() 
    df["description"] = clean_text(raw["description"])
    df["description_upper"] = df["description"].str.upper()
    df["quantity"] = pd.to_numeric(raw["quantity"], errors="coerce").round().astype("Int64")
    df["unit_price"] = pd.to_numeric(raw["unit_price"], errors="coerce").round(2)
    df["customer_id"] = pd.to_numeric(raw["customer_id"], errors="coerce").round().astype("Int64")
    df["is_guest"] = df["customer_id"].isna()
    df["invoice_ts_utc"] = to_utc(parse_dates(raw["invoice_date_raw"]), timezone)
    df["invoice_date"] = df["invoice_ts_utc"].dt.date
    df["country"] = clean_text(raw["country"]).fillna("Unspecified").replace(COUNTRY_FORMATS)
    return df


# --- Reject ---
def find_rejects(df):
    """Validates dataframe rows against business rules and flags rejection reasons."""
    def yes(condition):
        return condition.fillna(False).to_numpy(dtype=bool)

    checks = [
        ("MISSING_INVOICE_NO", yes(df["invoice_no"].isna())),
        ("INVALID_INVOICE_DATE", yes(df["invoice_ts_utc"].isna())),
        ("MISSING_STOCK_CODE", yes(df["stock_code"].isna())),
        ("NON_CATALOG_CODE", yes(~df["stock_code"].str.match(CATALOG_CODE))),
        ("INVALID_QUANTITY", yes(df["quantity"].isna())),
        ("INVALID_PRICE", yes(df["unit_price"].isna())),
        ("NON_POSITIVE_PRICE", yes(df["unit_price"] <= 0)),  
    ]
    reasons = np.select([mask for _, mask in checks], [name for name, _ in checks], default="")
    return pd.Series(reasons, index=df.index)


def find_duplicates(df):
    """Identifies duplicate rows within the same source or across different sources based on priority order."""
    seen_before = df.duplicated(subset=DUPLICATE_KEY, keep="first")
    seen_in_same_source = df.duplicated(subset=DUPLICATE_KEY + ["source"], keep="first")
    reasons = np.select(
        [seen_in_same_source, seen_before],
        ["DUPLICATE_WITHIN_SOURCE", "DUPLICATE_CROSS_SOURCE"], 
        default=""
    )
    return pd.Series(reasons, index=df.index)


# Products and categories
def load_category_rules(path):
    """Loads keyword mapping rules for product categorization from a CSV file."""
    rules = pd.read_csv(path)
    return {category: set(words) for category, words in rules.groupby("category", sort=False)["keyword"]}


def pick_category(description, rules):
    """Matches product description keywords against category rules to assign a category."""
    words = set(re.findall(r"[A-Z0-9'-]+", description.upper()))
    for category, keywords in rules.items():
        if words & keywords:
            return category, "rule"
    return DEFAULT_CATEGORY, "default"


def build_products(accepted, rules):
    """Aggregates accepted transaction data to build a master catalog of unique products and their categories."""
    counts = (
        accepted.dropna(subset=["description"])
        .groupby(["stock_code", "description_upper"]).size().reset_index(name="n")
        .sort_values(["stock_code", "n", "description_upper"], ascending=[True, False, True])
    )
    canonical = counts.drop_duplicates("stock_code").set_index("stock_code")["description_upper"]

    by_code = accepted.groupby("stock_code")
    products = pd.DataFrame({
        "n_raw_description_variants": by_code["description"].nunique(),
        "n_description_variants": by_code["description_upper"].nunique(),
    })
    products["has_inconsistent_description"] = products["n_raw_description_variants"] > 1
    products["first_seen_date"] = by_code["invoice_date"].min()
    products["last_seen_date"] = by_code["invoice_date"].max()
    products["description"] = canonical.reindex(products.index).fillna("SIN DESCRIPCION")
    categories = products["description"].map(lambda text: pick_category(text, rules))
    products["category"] = categories.str[0]
    products["category_source"] = categories.str[1]
    return products.reset_index()[[
        "stock_code", "description", "category", "category_source",
        "n_raw_description_variants", "n_description_variants",
        "has_inconsistent_description", "first_seen_date", "last_seen_date"
    ]]


# --- Glue all together ---
def transform(raw_by_source, priority, timezone, rules):
    """Concatenates sources by priority, standardizes, validates, filters rejects/duplicates, and splits into sales/returns/products."""
    raw = pd.concat([raw_by_source[source] for source in priority], ignore_index=True) 
    df = standardize(raw, timezone)

    reason = find_rejects(df)
    duplicates = find_duplicates(df[reason == ""]) 
    reason.loc[duplicates.index] = duplicates
    accepted = df[reason == ""].copy()

    rejected = raw.loc[reason != "", [c for c in REJECT_COLUMNS if c != "reason"]].copy()
    rejected.insert(2, "reason", reason[reason != ""])

    is_return = accepted["quantity"] <= 0
    sales = accepted[~is_return].copy()
    sales["quantity"] = sales["quantity"].astype("int64")
    sales["gross_revenue"] = (sales["quantity"] * sales["unit_price"]).round(2)

    returns = accepted[is_return].copy()
    returns["quantity_returned"] = (-returns["quantity"]).astype("int64")
    returns["return_amount"] = (returns["quantity_returned"] * returns["unit_price"]).round(2)
    returns["movement_type"] = np.where(returns["invoice_no"].str.startswith("C"), "RETURN", "ADJUSTMENT")

    products = build_products(accepted, rules)
    stats = {
        "rows_in": len(raw),
        "sales_rows": len(sales),
        "returns_rows": len(returns),
        "rejected_rows": len(rejected),
        "products": len(products),
        "guest_sales_rows": int(sales["is_guest"].sum()),
        "rejected_by_reason": {k: int(v) for k, v in rejected["reason"].value_counts().items()},
        "date_min": str(accepted["invoice_ts_utc"].min()),
        "date_max": str(accepted["invoice_ts_utc"].max()),
    }
    return {"sales": sales, "returns": returns, "rejected": rejected, "products": products, "stats": stats}


def transform_staged(extracted, priority, timezone, rules_file, staging_dir):
    """Transformation task: reads raw staging parquet files, applies transformations, and saves clean parquet results."""
    raw_by_source = {item["source"]: pd.read_parquet(item["path"]) for item in extracted}
    result = transform(raw_by_source, priority, timezone, load_category_rules(Path(rules_file)))

    paths = {}
    for name in ["sales", "returns", "rejected", "products"]:
        paths[name] = str(Path(staging_dir) / f"clean_{name}.parquet")
        result[name].to_parquet(paths[name], index=False)
    return {"paths": paths, "stats": result["stats"]}