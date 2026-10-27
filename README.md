# DataMart de ventas minoristas · Pipeline ETL & Data Warehouse

Solución integral de ingeniería de datos para **DataMart S.A.S.** que automatiza la ingesta, limpieza, validación de calidad, transformación y carga analítica de transacciones de ventas y devoluciones en un Data Warehouse PostgreSQL, completamente orquestado con **Apache Airflow 3** en contenedores **Docker Compose** e integrado con un microservicio REST en **FastAPI** para el catálogo de productos.

---

## 🌐 Enlaces y Documentación

- **Sitio web de documentación interactiva (Docusaurus):** [https://gen-lang-client-0165987641.web.app](https://gen-lang-client-0165987641.web.app)
- **Documento de decisiones técnicas:** Detalle de arquitectura, reglas de negocio, resolución de casos ambiguos e idempotencia disponible en el sitio web y en [`documentation/docs/decisiones.md`](../documentation/docs/decisiones.md).
- **Consultas SQL de validación de negocio:** [`sql/queries/queries.sql`](./sql/queries/queries.sql).

---

## 🏗️ Arquitectura del Sistema

```
[Fuentes Crudas: data.csv + online_retail_II.csv]
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
[extract_history_sales]     [extract_daily_sales]
       │                               │
       └───────────────┬───────────────┘
                       ▼
            (Staging Parquet en disco)
                       │
                       ▼
          [validate_and_transform] ◄─── Consulta catálogo [FastAPI: products-api]
                       │
       ┌───────────────┼──────────────────────────────┐
       ▼               ▼                              ▼
(clean_sales)   (clean_returns)              (rejected_records)
       │               │                              │
       └───────────────┬──────────────────────────────┘
                       ▼
                  [load_to_db] ───► PostgreSQL DW (Transacción atómica + Recálculo diario)
                       │
                       ▼
              [run_quality_check] ───► Validación de integridad financiera y filas
```

### Componentes de la infraestructura Docker
1. **`airflow-apiserver`** (puerto `8080`): Interfaz web moderna y API de Apache Airflow 3.3.2 con autenticación preconfigurada.
2. **`airflow-scheduler`**: Planificador que detecta y ejecuta automáticamente los DAGs.
3. **`airflow-dag-processor`**: Procesador asíncrono de DAGs.
4. **`postgres-airflow`**: Base de datos dedicada exclusivamente a los metadatos internos de Airflow.
5. **`postgres-dw`** (puerto `5433`): Repositorio analítico destino (Data Warehouse) con DDL inicializado automáticamente al arrancar.
6. **`products-api`** (puerto `8000`): Microservicio REST FastAPI que expone el catálogo con paginación, búsqueda por código y estado.

---

## 🚀 Guía de inicio rápido: Paso a paso para montar y ejecutar

Sigue estos sencillos pasos para tener todo el entorno funcionando y validado en **menos de 10 minutos**:

### 1. Requisitos previos
- **Docker** y **Docker Compose** (Docker Desktop en Windows/Mac o Docker Engine en Linux con Compose v2).
- Mínimo 4 GB de memoria RAM asignada a Docker.
- Git.

---

### 2. Clonar el repositorio y entrar al proyecto
```bash
git clone https://github.com/Pbyte5/prueba_desempe-o_analitica.git
cd prueba_desempe-o_analitica
```
*(Si ya tienes la carpeta descomprimida, simplemente abre una terminal en la raíz del proyecto).*

---

### 3. Configurar variables de entorno
Copia el archivo de plantilla `.env.example` para crear el `.env`:

- **En Linux / macOS / Git Bash:**
  ```bash
  cp .env.example .env
  ```
- **En Windows (PowerShell):**
  ```powershell
  Copy-Item .env.example .env
  ```

> ℹ️ **Nota:** Las variables en `.env.example` ya vienen completamente configuradas con valores funcionales por defecto (puertos, usuarios, contraseñas, rutas y parámetros operativos). No necesitas modificar nada a menos que desees personalizar credenciales.

---

### 4. Verificar archivos de datos de entrada
Asegúrate de que los datasets estén en la carpeta `data/raw/` y las reglas en `seeds/`:
- `data/raw/data.csv` (ventas diarias operacionales)
- `data/raw/online_retail_II.csv` (historial transaccional extendido)
- `seeds/category.csv` (matriz de clasificación por palabras clave de categorías)

*(Estos archivos ya se encuentran incluidos y versionados en el repositorio).*

---

### 5. Levantar el entorno con Docker Compose
Ejecuta el siguiente comando para construir y levantar todos los servicios en segundo plano:

```bash
docker compose up -d --build
```
*(O `docker-compose up -d --build` si utilizas Compose v1).*

Docker descargará las imágenes base, compilará el contenedor de Airflow con las dependencias del proyecto (`uv`, `pandas`, `psycopg`), compilará la API de catálogo e inicializará las bases de datos.

Para verificar que todos los servicios estén arriba y saludables (`healthy`), ejecuta:
```bash
docker compose ps
```
Deberás ver los 6 contenedores (`airflow-apiserver`, `airflow-scheduler`, `airflow-dag-processor`, `postgres-airflow`, `postgres-dw`, `products-api`) en estado `Up (healthy)` o `Up`.

---

### 6. Acceder a la interfaz web de Airflow
Una vez arriba los servicios, abre en tu navegador:
- **URL:** [http://localhost:8080](http://localhost:8080)
- **Usuario:** `admin`
- **Contraseña:** `admin123`

---

### 7. Validar Airflow Connections y Variables automáticas
El entorno inyecta automáticamente las conexiones y variables necesarias al iniciar el contenedor mediante variables de entorno en `docker-compose.yml`, cumpliendo con la exigencia de no requerir intervención manual:

#### A. Conexión analítica (`datamart`)
- **En la UI de Airflow:** Ve a **Admin** $\to$ **Connections**. Verás la conexión `datamart` apuntando a `postgresql://datamart:datamartpass@postgres-dw:5432/datamart_dw`.
- **Por CLI:**
  ```bash
  docker exec datamart-airflow-scheduler-1 airflow connections get datamart
  ```

#### B. Variables operativas del pipeline
- **En la UI de Airflow:** Ve a **Admin** $\to$ **Variables**. Verás las siguientes variables operativas inicializadas:
  - `datamart_history_files`: `raw/online_retail_II.csv`
  - `datamart_daily_files`: `raw/data.csv`
  - `datamart_source_priority`: `history,daily`
  - `datamart_source_tz`: `Europe/London`
  - `datamart_products_api_url`: `http://products-api:8000`
- **Por CLI:**
  ```bash
  docker exec datamart-airflow-scheduler-1 airflow variables get datamart_source_priority
  ```

---

### 8. Ejecución y monitoreo del DAG
El DAG `datamart_mall_etl` está configurado con `DAGS_ARE_PAUSED_AT_CREATION: "false"`, por lo que el Scheduler lo ejecutará de forma automática al detectar el archivo.

- Para consultar el estado o disparar una ejecución manual inmediata:
  - **Desde la UI:** Haz clic en el botón de **Play (Trigger DAG)** sobre `datamart_mall_etl`.
  - **Desde la CLI:**
    ```bash
    docker exec datamart-airflow-scheduler-1 airflow dags trigger datamart_mall_etl
    ```
- **Flujo de tareas orquestadas:**
  1. `extract_history_sales` & `extract_daily_sales` (lectura sin tipos forzados, unificación de nombres de columnas y conversión a Parquet en staging).
  2. `validate_and_transform` (limpieza, normalización a mayúsculas, cálculo de UTC, separación ventas/devoluciones, deduplicación entre fuentes y consulta al API de catálogo).
  3. `load_to_db` (carga atómica masiva vía `COPY`, truncado previo para idempotencia y recálculo de `fact_daily_product`).
  4. `run_quality_check` (auditoría financiera y validación de que $100\%$ de las filas crudas fueron contabilizadas).

---

### 9. Validar los datos cargados en PostgreSQL (Data Warehouse)
El repositorio analítico está disponible en el puerto `5433` (para evitar colisiones con instancias locales de PostgreSQL):
- **Host:** `localhost` (puerto `5433` externo / `5432` interno)
- **Base de datos:** `datamart_dw`
- **Usuario:** `datamart`
- **Contraseña:** `datamartpass`

Puedes verificar el conteo de registros en cada tabla ejecutando:

**En Linux / macOS / Bash:**
```bash
docker exec datamart-postgres-dw-1 psql -U datamart -d datamart_dw -c "
SELECT 'fact_sales' AS tabla, COUNT(*) FROM fact_sales
UNION ALL SELECT 'fact_returns', COUNT(*) FROM fact_returns
UNION ALL SELECT 'dim_product', COUNT(*) FROM dim_product
UNION ALL SELECT 'fact_daily_product', COUNT(*) FROM fact_daily_product
UNION ALL SELECT 'rejected_records', COUNT(*) FROM rejected_records;"
```

**En Windows (PowerShell):**
```powershell
docker exec datamart-postgres-dw-1 psql -U datamart -d datamart_dw -c "SELECT 'fact_sales' AS tabla, COUNT(*) FROM fact_sales UNION ALL SELECT 'fact_returns', COUNT(*) FROM fact_returns UNION ALL SELECT 'dim_product', COUNT(*) FROM dim_product UNION ALL SELECT 'fact_daily_product', COUNT(*) FROM fact_daily_product UNION ALL SELECT 'rejected_records', COUNT(*) FROM rejected_records;"
```

**Resultados esperados:**
| Tabla | Registros esperados | Propósito |
| :--- | :---: | :--- |
| `dim_product` | **3,805** | Catálogo canónico de productos únicos enriquecidos con categoría y métricas de consistencia |
| `fact_sales` | **522,502** | Líneas de ventas válidas (`quantity > 0` y `unit_price > 0`) |
| `fact_returns` | **8,668** | Devoluciones y ajustes (`quantity <= 0`) clasificados como `RETURN` o `ADJUSTMENT` |
| `rejected_records` | **552,648** | Log detallado de registros descartados con causa raíz y fuente |
| `fact_daily_product` | **276,995** | Tabla agregada de revenue bruto, monto de devoluciones y **revenue neto** por producto y día |

*(Suma de trazabilidad exacta: $522.502 + 8.668 + 552.648 = 1.083.818$ filas crudas, conciliación al $100\%$).*

---

### 10. Validar el API del catálogo de productos (FastAPI)
El microservicio de catálogo expone el catálogo real almacenado en PostgreSQL:
- **Documentación Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Healthcheck:** [http://localhost:8000/health](http://localhost:8000/health)
- **Listado paginado de productos:**
  ```bash
  curl -s "http://localhost:8000/products?offset=0&limit=5"
  ```
- **Consulta de producto específico por código:**
  ```bash
  curl -s "http://localhost:8000/products/85123A"
  ```

---

### 11. Ejecutar las consultas SQL de validación de negocio (Preguntas 1 a 7)
El archivo [`sql/queries/queries.sql`](./sql/queries/queries.sql) contiene las consultas que responden cada una de las preguntas de negocio del enunciado (evolución mensual de ventas netas, top productos, categorías con más devoluciones, comparación clientes identificados vs invitados, etc.).

Para ejecutarlas todas y ver los resultados en consola:

- **En Linux / macOS / Git Bash:**
  ```bash
  docker exec -i datamart-postgres-dw-1 psql -U datamart -d datamart_dw < sql/queries/queries.sql
  ```
- **En Windows (PowerShell):**
  ```powershell
  Get-Content sql/queries/queries.sql -Raw | docker exec -i datamart-postgres-dw-1 psql -U datamart -d datamart_dw
  ```

---

### 12. Detener el entorno
Para detener los contenedores:
```bash
docker compose down
```
Si deseas detenerlos y eliminar los volúmenes de datos para iniciar una prueba completamente limpia desde cero:
```bash
docker compose down -v
```

---

## 📊 Modelo de Datos del Repositorio Analítico

El Data Warehouse fue modelado siguiendo un esquema dimensional optimizado para el análisis de ventas, devoluciones y calidad de datos:

![Diagrama del modelo de datos](./img/modelo-datos.png)

### Justificación de diseño
- **Separación de ventas y devoluciones:** Evita mezclar signos negativos en el cálculo de totales y permite auditorías claras de devoluciones sin distorsionar el volumen bruto de órdenes.
- **Tabla física `fact_daily_product`:** Cumple el requerimiento de negocio de "calcular y almacenar" el revenue neto por producto y día.
- **Tabla de auditoría `rejected_records`:** Conserva el registro fiel de cada fila rechazada con su motivo (`NON_CATALOG_CODE`, `NON_POSITIVE_PRICE`, `DUPLICATE_CROSS_SOURCE`, `DUPLICATE_WITHIN_SOURCE`), permitiendo auditar la calidad de los datos de los proveedores.

---

## 🛡️ Idempotencia y Calidad de Datos

- **Idempotencia:** La tarea `load_to_db` se ejecuta en una transacción única (`TRUNCATE ... RESTART IDENTITY` $\to$ Carga masiva $\to$ Recálculo de agregaciones $\to$ `COMMIT`). Si ocurre cualquier fallo, se ejecuta `ROLLBACK`. Ejecutar el DAG múltiples veces con los mismos datos genera exactamente el mismo estado sin duplicados ni inconsistencias.
- **Data Quality:** La tarea final `run_quality_check` valida que:
  1. La suma de ventas + devoluciones + rechazados sea exactamente igual a las filas de entrada.
  2. El revenue bruto de `fact_daily_product` concilie al centavo con `fact_sales`.
  3. El monto de devoluciones de `fact_daily_product` concilie con `fact_returns`.
  4. Ningún registro presente discrepancia en la fórmula `net_revenue = gross_revenue - returns_amount`.
