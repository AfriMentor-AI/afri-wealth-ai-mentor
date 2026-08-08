# MLflow tracking server for AfriMentor AI research workspace (card D1.4)
FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1 PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10
# psycopg[binary] is psycopg 3 — required by the `postgresql+psycopg://` dialect
# used in MLFLOW_BACKEND_URI (and every other service URI). psycopg2-binary
# provides the `psycopg2` module, not `psycopg`, so the +psycopg driver can't import it.
RUN pip install mlflow==2.19.0 "psycopg[binary]==3.2.3"

RUN useradd --create-home --uid 10001 mlflow
WORKDIR /mlflow
RUN chown mlflow:mlflow /mlflow
USER mlflow

EXPOSE 5000

# Backend: Postgres in prod, SQLite in dev (mounted volume)
# Artifacts: local volume in dev, S3 in prod
# Shell form (not exec form) so ${MLFLOW_BACKEND_URI}/${MLFLOW_ARTIFACT_ROOT}
# are expanded by the shell at runtime; an exec-form CMD passes them to mlflow
# as literal, unexpanded strings. `exec` hands PID to mlflow for clean signals.
CMD exec mlflow server \
    --host 0.0.0.0 \
    --port 5000 \
    --backend-store-uri "${MLFLOW_BACKEND_URI}" \
    --default-artifact-root "${MLFLOW_ARTIFACT_ROOT}"
