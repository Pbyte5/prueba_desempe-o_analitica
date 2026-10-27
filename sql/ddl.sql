CREATE TABLE IF NOT EXISTS dim_product (
    stock_code                  TEXT PRIMARY KEY,      
    description                 TEXT NOT NULL,        
    category                    TEXT NOT NULL,
    category_source             TEXT NOT NULL CHECK (category_source IN ('rule', 'default')),
    n_raw_description_variants  INTEGER NOT NULL,      
    n_description_variants      INTEGER NOT NULL,
    has_inconsistent_description BOOLEAN NOT NULL,
    first_seen_date             DATE NOT NULL,
    last_seen_date              DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_sales (
    sale_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    invoice_no      TEXT NOT NULL,
    stock_code      TEXT NOT NULL REFERENCES dim_product (stock_code),
    customer_id     INTEGER,                           
    is_guest        BOOLEAN NOT NULL,
    country         TEXT NOT NULL,
    invoice_ts_utc  TIMESTAMPTZ NOT NULL,
    invoice_date    DATE NOT NULL,                     
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    unit_price      NUMERIC(12, 2) NOT NULL CHECK (unit_price > 0),
    gross_revenue   NUMERIC(14, 2) NOT NULL,           
    source          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_returns (
    return_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    invoice_no         TEXT NOT NULL,
    stock_code         TEXT NOT NULL REFERENCES dim_product (stock_code),
    customer_id        INTEGER,
    is_guest           BOOLEAN NOT NULL,
    country            TEXT NOT NULL,
    invoice_ts_utc     TIMESTAMPTZ NOT NULL,
    invoice_date       DATE NOT NULL,
    quantity_returned  INTEGER NOT NULL CHECK (quantity_returned >= 0),   
    unit_price         NUMERIC(12, 2) NOT NULL CHECK (unit_price > 0),
    return_amount      NUMERIC(14, 2) NOT NULL,                           
    movement_type      TEXT NOT NULL CHECK (movement_type IN ('RETURN', 'ADJUSTMENT')),
    source             TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS fact_daily_product (
    invoice_date    DATE NOT NULL,
    stock_code      TEXT NOT NULL REFERENCES dim_product (stock_code),
    units_sold      INTEGER NOT NULL,
    units_returned  INTEGER NOT NULL,
    gross_revenue   NUMERIC(14, 2) NOT NULL,
    returns_amount  NUMERIC(14, 2) NOT NULL,
    net_revenue     NUMERIC(14, 2) NOT NULL,
    PRIMARY KEY (invoice_date, stock_code)
);

CREATE TABLE IF NOT EXISTS rejected_records (
    reject_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source            TEXT NOT NULL,       
    source_row        INTEGER NOT NULL,    
    reason            TEXT NOT NULL,
    invoice_no        TEXT,
    stock_code        TEXT,
    description       TEXT,
    quantity          TEXT,
    unit_price        TEXT,
    invoice_date_raw  TEXT,
    customer_id       TEXT,
    country           TEXT,
    UNIQUE (source, source_row)
);

CREATE INDEX IF NOT EXISTS ix_fact_sales_date    ON fact_sales (invoice_date);
CREATE INDEX IF NOT EXISTS ix_fact_sales_product ON fact_sales (stock_code);
CREATE INDEX IF NOT EXISTS ix_fact_returns_date  ON fact_returns (invoice_date);
CREATE INDEX IF NOT EXISTS ix_rejected_reason    ON rejected_records (source, reason);
