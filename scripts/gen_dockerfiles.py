#!/usr/bin/env python3
"""Regenerate lean, multi-stage Dockerfiles + .dockerignore for every service (card O1.2).

Optimizations vs the original single-stage image:
  * Multi-stage: a builder compiles wheels into a venv; the runtime copies only that
    venv, so build toolchain / caches never reach the final image.
  * Split deps: pytest lives in requirements-dev.txt and is NOT installed at runtime.
  * Non-root: runs as an unprivileged `app` user.
  * .dockerignore: keeps tests, caches and local keys out of the build context.
  * curl-free HEALTHCHECK via stdlib urllib; no extra apt packages.

Run: python scripts/gen_dockerfiles.py
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"

# service -> exposed port (kept identical to the compose wiring).
PORTS = {
    "api-gateway": 8000,
    "auth-user-service": 8001,
    "intake-profiling-service": 8002,
    "chat-orchestration-service": 8003,
    "persona-prompt-service": 8004,
    "rag-corpus-service": 8005,
    "goals-milestones-service": 8006,
    "progress-gamification-service": 8007,
    "insight-library-service": 8008,
    "feedback-service": 8009,
    "research-evaluation-service": 8010,
    "voice-service": 8011,
    "notification-service": 8012,
}

# Deps that are test-only and must be stripped from the runtime image.
DEV_ONLY = {"pytest"}


def dockerfile(service: str, port: int) -> str:
    return f"""# syntax=docker/dockerfile:1
# Lean multi-stage image for {service} (card O1.2).
# Stage 1 builds a self-contained venv; stage 2 ships only the venv + app code.

FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
# Isolated venv so we can copy the whole tree into the runtime stage verbatim.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \\
    PATH="/opt/venv/bin:$PATH" PORT={port}
# Unprivileged runtime user.
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app app ./app
# App owns its workdir so a standalone run (default SQLite) can write locally.
RUN chown app:app /app
USER app

EXPOSE {port}
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \\
  CMD python -c "import urllib.request,sys; \\
sys.exit(0) if urllib.request.urlopen('http://localhost:{port}/health').status==200 else sys.exit(1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "{port}"]
"""


DOCKERIGNORE = """\
# Keep the build context tiny and the image reproducible.
tests/
**/__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.venv/
venv/
requirements-dev.txt
*.md
.env
.env.*
*.pem
*.key
"""


def split_requirements(req_path: pathlib.Path) -> None:
    """Move DEV_ONLY packages from requirements.txt into requirements-dev.txt."""
    lines = req_path.read_text(encoding="utf-8").splitlines()
    runtime, dev = [], []
    for line in lines:
        pkg = line.strip().split("==")[0].split("[")[0].lower()
        (dev if pkg in DEV_ONLY else runtime).append(line)
    req_path.write_text("\n".join(runtime).rstrip() + "\n", encoding="utf-8")
    dev_path = req_path.parent / "requirements-dev.txt"
    header = "# Test-only deps (not installed in the runtime image). Install: pip install -r requirements-dev.txt\n-r requirements.txt\n"
    body = "\n".join(dev).rstrip()
    dev_path.write_text(header + (body + "\n" if body else ""), encoding="utf-8")


def main() -> None:
    for service, port in PORTS.items():
        sdir = SERVICES / service
        if not sdir.exists():
            print(f"  ! skipping missing {service}")
            continue
        (sdir / "Dockerfile").write_text(dockerfile(service, port), encoding="utf-8")
        (sdir / ".dockerignore").write_text(DOCKERIGNORE, encoding="utf-8")
        split_requirements(sdir / "requirements.txt")
        print(f"  [ok] {service} (:{port})")
    print("Regenerated Dockerfiles, .dockerignore, and split requirements for all services.")


if __name__ == "__main__":
    main()
