# MLflow tracking server for AfriMentor AI research workspace (card D1.4)
FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1
RUN pip install mlflow==2.19.0 psycopg2-binary==2.9.10

RUN useradd --create-home --uid 10001 mlflow
WORKDIR /mlflow
RUN chown mlflow:mlflow /mlflow
USER mlflow

EXPOSE 5000

# Backend: Postgres in prod, SQLite in dev (mounted volume)
# Artifacts: local volume in dev, S3 in prod
CMD ["mlflow", "server", \
     "--host", "0.0.0.0", \
     "--port", "5000", \
     "--backend-store-uri", "${MLFLOW_BACKEND_URI}", \
     "--default-artifact-root", "${MLFLOW_ARTIFACT_ROOT}"]
