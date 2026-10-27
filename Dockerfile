ARG AIRFLOW_VERSION=3.3.2
FROM apache/airflow:${AIRFLOW_VERSION}

ARG AIRFLOW_VERSION

# Stagging route
USER root
RUN mkdir -p /opt/airflow/staging && chown airflow:0 /opt/airflow/staging && chmod 775 /opt/airflow/staging
USER airflow

COPY requirements.txt /tmp/requirements.txt

# Airflow install.
RUN PYTHON_VERSION="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" \
    && pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /tmp/requirements.txt \
       --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"
