# syntax=docker/dockerfile:1
# Lean multi-stage image for rag-corpus-service (card O1.2).
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
# Pre-download the ONNX embedding model (~80 MB) so it is baked into the image.
# Without this, the first query triggers a live download that takes >10 s and
# exceeds the chat-orchestration-service HTTP timeout, silently dropping all citations.
# The builder runs as root, so the cache lands at /root/.cache/chroma.
RUN python -c 'from chromadb.utils.embedding_functions import DefaultEmbeddingFunction; DefaultEmbeddingFunction()(["warmup"])'

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" PORT=8005
# Unprivileged runtime user.
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
# Copy the pre-downloaded ONNX model cache and hand ownership to the app user.
COPY --from=builder --chown=app:app /root/.cache/chroma /home/app/.cache/chroma
COPY --chown=app:app app ./app
# App owns its workdir so a standalone run (default SQLite) can write locally.
RUN chown app:app /app
USER app

EXPOSE 8005
HEALTHCHECK --interval=10s --timeout=3s --start-period=180s --retries=5 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0) if urllib.request.urlopen('http://localhost:8005/health').status==200 else sys.exit(1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
