import os
from contextlib import asynccontextmanager
from typing import Annotated

import psycopg
from fastapi import FastAPI, HTTPException, Query
from psycopg.rows import dict_row
from pydantic import BaseModel


DATABASE_CONFIG = {
    "host": os.environ.get("DW_HOST", "postgres-dw"),
    "port": os.environ.get("DW_PORT", "5432"),
    "dbname": os.environ["DW_DB"],
    "user": os.environ["DW_USER"],
    "password": os.environ["DW_PASSWORD"],
}


class Product(BaseModel):
    code: str
    name: str
    category: str
    supplier_country: str
    is_active: bool


class ProductPage(BaseModel):
    items: list[Product]
    total: int
    offset: int
    limit: int


def get_connection():
    return psycopg.connect(**DATABASE_CONFIG, row_factory=dict_row)


@asynccontextmanager
async def lifespan(_: FastAPI):
    with get_connection() as connection:
        connection.execute(
            """
            ALTER TABLE dim_product
                ADD COLUMN IF NOT EXISTS supplier_country TEXT NOT NULL DEFAULT 'Unspecified',
                ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE
            """
        )
        connection.execute(
            """
            ALTER TABLE dim_product
                DROP CONSTRAINT IF EXISTS dim_product_category_source_check
            """
        )
        connection.execute(
            """
            ALTER TABLE dim_product
                ADD CONSTRAINT dim_product_category_source_check
                CHECK (category_source IN ('rule', 'default', 'api'))
            """
        )
    yield


app = FastAPI(title="DataMart Product Catalog API", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health():
    with get_connection() as connection:
        connection.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/products", response_model=ProductPage)
def list_products(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    with get_connection() as connection:
        total = connection.execute("SELECT COUNT(*) AS total FROM dim_product").fetchone()["total"]
        rows = connection.execute(
            """
            SELECT stock_code AS code,
                   UPPER(REGEXP_REPLACE(BTRIM(description), '[[:space:]]+', ' ', 'g')) AS name,
                   category,
                   supplier_country, is_active
            FROM dim_product
            ORDER BY stock_code
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        ).fetchall()
    return {"items": rows, "total": total, "offset": offset, "limit": limit}


@app.get("/products/{code}", response_model=Product)
def get_product(code: str):
    normalized_code = "".join(code.upper().split())
    with get_connection() as connection:
        product = connection.execute(
            """
            SELECT stock_code AS code,
                   UPPER(REGEXP_REPLACE(BTRIM(description), '[[:space:]]+', ' ', 'g')) AS name,
                   category,
                   supplier_country, is_active
            FROM dim_product
            WHERE stock_code = %s
            """,
            (normalized_code,),
        ).fetchone()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
