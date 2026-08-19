# syntax=docker/dockerfile:1
# Lean multi-stage image for auth-user-service (card O1.2).
# Stage 1 builds a self-contained venv; stage 2 ships only the venv + app code.

FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10
WORKDIR /app
# Isolated venv so we can copy the whole tree into the runtime stage verbatim.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" PORT=8001
# Unprivileged runtime user.
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./alembic.ini
COPY --chown=app:app docker-entrypoint.sh ./docker-entrypoint.sh
# App owns its workdir so a standalone run (default SQLite) can write locally.
RUN chown app:app /app && chmod +x docker-entrypoint.sh
# Pre-create with app ownership so the named volume mounted here in
# docker-compose.yml (auth_dev_keys) inherits it on first creation — Docker
# copies a fresh named volume's initial content/ownership from the image
# directory it's mounted over, and the container itself runs as uid 10001,
# not root, so it can't chown this after the fact.
RUN mkdir -p /dev_keys && chown app:app /dev_keys
USER app

EXPOSE 8001
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0) if urllib.request.urlopen('http://localhost:8001/health').status==200 else sys.exit(1)"

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
