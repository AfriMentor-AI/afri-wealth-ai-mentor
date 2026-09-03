# Lean image using the existing verified local base
FROM afrimentor-cloud-chat-orchestration-service:latest

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" PORT=8006

WORKDIR /app
COPY --chown=app:app app ./app
RUN chown -R app:app /app
USER app

EXPOSE 8006
HEALTHCHECK --interval=20s --timeout=10s --start-period=40s --retries=5 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0) if urllib.request.urlopen('http://localhost:8006/health').status==200 else sys.exit(1)"

ENTRYPOINT []
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8006"]
