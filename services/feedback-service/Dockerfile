# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8009

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8009
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5   CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://localhost:8009/health').status==200 else sys.exit(1)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8009"]
