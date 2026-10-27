# DataMart: catálogo interno de productos

El servicio `products-api` expone el catálogo almacenado en `dim_product` de
PostgreSQL (`postgres-dw`); no mantiene un catálogo duplicado en memoria. Al
iniciarse, agrega las columnas de país de origen y estado si la base ya existía.
Como las transacciones disponibles no incluyen el país del proveedor ni el
estado del producto, esos campos empiezan con `Unspecified` y `true`.

## Endpoints

- `GET /products?offset=0&limit=100`: lista paginada, ordenada por código.
  `limit` admite valores entre 1 y 500. La respuesta incluye `items`, `total`,
  `offset` y `limit`.
- `GET /products/{code}`: consulta por código, normalizado a mayúsculas y sin
  espacios; devuelve 404 si no existe.
- `GET /health`: verifica la conexión con PostgreSQL.

Cada producto devuelve `code`, `name` (descripción normalizada), `category`,
`supplier_country` e `is_active`.

## Pipeline

Airflow consulta el API en `http://products-api:8000` antes de transformar los
datos. Las categorías ya registradas en la dimensión de productos tienen
prioridad; los códigos nuevos se categorizan con `seeds/category.csv`. Por eso,
la primera ejecución puede poblar el catálogo a partir de las transacciones y
las siguientes reutilizan la categoría persistida en PostgreSQL.

Para ejecutar el API sin integrarlo al pipeline, configure
`DATAMART_PRODUCTS_API_URL` como cadena vacía; el pipeline usará las reglas CSV.
Si el API está configurado pero no responde, la tarea falla explícitamente para
que Airflow pueda reintentarla, en lugar de ocultar el error.

Con Docker Compose, el servicio queda disponible en `http://localhost:8000`
(configurable mediante `PRODUCTS_API_HOST_PORT`).