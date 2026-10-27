-- ## P1. ¿Cuál fue la evolución mensual de las ventas netas (descontando devoluciones)?
SELECT date_trunc('month', invoice_date)::date AS month,
       SUM(gross_revenue)  AS gross_revenue,
       SUM(returns_amount) AS returns_amount,
       SUM(net_revenue)    AS net_revenue
FROM fact_daily_product
GROUP BY 1
ORDER BY 1;

-- ## P2a. ¿Qué categorías generaron más revenue bruto?
SELECT p.category,
       SUM(d.gross_revenue) AS gross_revenue,
       SUM(d.net_revenue)   AS net_revenue
FROM fact_daily_product d
JOIN dim_product p USING (stock_code)
GROUP BY p.category
ORDER BY gross_revenue DESC;

-- ## P2b. ¿Qué categorías tuvieron mayor proporción de devoluciones?
SELECT p.category,
       ROUND(100.0 * SUM(d.returns_amount) / NULLIF(SUM(d.gross_revenue), 0), 2) AS returns_pct_of_revenue,
       ROUND(100.0 * SUM(d.units_returned) / NULLIF(SUM(d.units_sold), 0), 2)    AS returns_pct_of_units
FROM fact_daily_product d
JOIN dim_product p USING (stock_code)
GROUP BY p.category
ORDER BY returns_pct_of_revenue DESC;

-- ## P3a. ¿Cuáles son los 10 productos con mayor revenue neto?
SELECT d.stock_code, p.description, p.category,
       SUM(d.net_revenue) AS net_revenue
FROM fact_daily_product d
JOIN dim_product p USING (stock_code)
GROUP BY d.stock_code, p.description, p.category
ORDER BY net_revenue DESC
LIMIT 10;

-- ## P3b. ¿Cuáles son los 10 productos con mayor tasa de devolución?
-- (unidades devueltas / unidades vendidas; se pide un mínimo de 100 unidades vendidas para que
--  un producto con una sola venta no encabece la lista)
SELECT d.stock_code, p.description, p.category,
       SUM(d.units_sold)     AS units_sold,
       SUM(d.units_returned) AS units_returned,
       ROUND(100.0 * SUM(d.units_returned) / SUM(d.units_sold), 2) AS return_rate_pct
FROM fact_daily_product d
JOIN dim_product p USING (stock_code)
GROUP BY d.stock_code, p.description, p.category
HAVING SUM(d.units_sold) >= 100
ORDER BY return_rate_pct DESC
LIMIT 10;

-- ## P4. ¿Qué países concentran la mayor parte de las transacciones y cómo varía el ticket promedio?
-- (transacción = factura; ticket = total de la factura)
WITH invoices AS (
    SELECT country, invoice_no, SUM(gross_revenue) AS invoice_total
    FROM fact_sales
    GROUP BY country, invoice_no
)
SELECT country,
       COUNT(*)                                           AS transactions,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_transactions,
       ROUND(AVG(invoice_total), 2)                       AS avg_ticket
FROM invoices
GROUP BY country
ORDER BY transactions DESC;

-- ## P5a. ¿Hay diferencias entre clientes identificados y transacciones sin customer ID?
WITH invoices AS (
    SELECT invoice_no, is_guest,
           SUM(gross_revenue) AS invoice_total,
           SUM(quantity)      AS units,
           COUNT(*)           AS lines
    FROM fact_sales
    GROUP BY invoice_no, is_guest
)
SELECT CASE WHEN is_guest THEN 'sin customer ID' ELSE 'identificado' END AS customer_type,
       COUNT(*)                     AS invoices,
       ROUND(AVG(invoice_total), 2) AS avg_ticket,
       ROUND(AVG(units), 1)         AS avg_units_per_invoice,
       ROUND(AVG(lines), 1)         AS avg_lines_per_invoice,
       ROUND(SUM(invoice_total), 2) AS gross_revenue
FROM invoices
GROUP BY is_guest
ORDER BY is_guest;

-- ## P5b. Impacto de incluir las transacciones sin customer ID (qué parte del total representan)
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE is_guest) / COUNT(*), 2)                          AS pct_of_sale_lines,
       ROUND(100.0 * SUM(gross_revenue) FILTER (WHERE is_guest) / SUM(gross_revenue), 2)      AS pct_of_gross_revenue
FROM fact_sales;

-- ## P6a. ¿Qué productos no tienen una descripción consistente?
-- (n_raw: escrituras distintas tal como llegaron, p. ej. CANDLE / Candle; n_description: tras pasar a mayúsculas)
SELECT stock_code, description AS canonical_description,
       n_raw_description_variants, n_description_variants
FROM dim_product
WHERE n_raw_description_variants > 1
ORDER BY n_description_variants DESC, n_raw_description_variants DESC, stock_code;

-- ## P6b. ¿Cuántos productos tienen descripciones inconsistentes y cuántos siguen siéndolo tras normalizar?
SELECT COUNT(*) FILTER (WHERE n_raw_description_variants > 1) AS codes_with_raw_variants,
       COUNT(*) FILTER (WHERE n_description_variants > 1)     AS codes_still_inconsistent_after_uppercase
FROM dim_product;

-- ## P6c. ¿Cuántos códigos únicos de producto existen en total?
SELECT (SELECT COUNT(*) FROM dim_product) AS valid_catalog_codes,
       (SELECT COUNT(DISTINCT stock_code) FROM rejected_records WHERE reason = 'NON_CATALOG_CODE')
                                          AS non_catalog_codes_rejected;

-- ## P7. Recomendación para el equipo de producto: productos de alto revenue que pierden mucho por devoluciones
-- (los números de esta consulta sustentan la recomendación de docs/RECOMENDACION.md)
SELECT d.stock_code, p.description, p.category,
       SUM(d.gross_revenue)  AS gross_revenue,
       SUM(d.returns_amount) AS returns_amount,
       ROUND(100.0 * SUM(d.returns_amount) / NULLIF(SUM(d.gross_revenue), 0), 2) AS returns_pct_of_revenue,
       p.n_raw_description_variants
FROM fact_daily_product d
JOIN dim_product p USING (stock_code)
GROUP BY d.stock_code, p.description, p.category, p.n_raw_description_variants
HAVING SUM(d.gross_revenue) >= 1000
ORDER BY returns_amount DESC
LIMIT 20;

-- ## Auditoría. ¿Qué se rechazó, de qué fuente y por qué?
SELECT source, reason, COUNT(*) AS rows_rejected
FROM rejected_records
GROUP BY source, reason
ORDER BY source, rows_rejected DESC;
