# DataMart de ventas minoristas

Proyecto de ingeniería y analítica de datos que integra archivos de ventas,
valida y transforma sus registros, y los carga en un repositorio analítico
PostgreSQL. El flujo se orquesta con Apache Airflow y Docker Compose; incluye
una API REST para consultar el catálogo de productos.

## Documentación

La arquitectura, las decisiones de calidad de datos, el modelo analítico, las
consultas SQL y la recomendación de negocio están documentadas en el sitio
Docusaurus:

**[Abrir la documentación del proyecto](https://gen-lang-client-0165987641.web.app)**


## Componentes principales

- **Apache Airflow:** orquesta extracción, transformación, carga y controles
  de calidad.
- **PostgreSQL:** almacena los hechos de ventas y devoluciones, la dimensión de
  productos y el registro de filas rechazadas.
- **API de productos:** permite consultar el catálogo que mantiene el almacén.
- **Docker Compose:** levanta los servicios del entorno local.

Consulta la documentación de Docusaurus para instrucciones de ejecución,
arquitectura, reglas del negocio, consultas y uso de la API.
