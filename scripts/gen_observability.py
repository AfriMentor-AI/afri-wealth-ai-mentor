#!/usr/bin/env python3
"""Wire Prometheus metrics + OpenTelemetry tracing + JSON logging into every service
(card O2.5).

Idempotent — safe to re-run after adding a new service or changing the shared
template. For each service in SERVICES:
  1. Copies scripts/_observability_module_template.py -> app/observability.py.
  2. Inserts `from .observability import instrument` + `instrument(app, SERVICE_NAME)`
     into main.py, right after the `app = FastAPI(...)` block (skipped if already
     present).
  3. Appends the required packages to requirements.txt (skipped if already present).
  4. For services in DB_SERVICES, inserts `instrument_db(engine)` into their
     database/session module right after `engine = create_engine(...)`.

Run: python scripts/gen_observability.py
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICES_DIR = ROOT / "services"
TEMPLATE = (ROOT / "scripts" / "_observability_module_template.py").read_text(encoding="utf-8")

SERVICES = [
    "api-gateway",
    "auth-user-service",
    "intake-profiling-service",
    "chat-orchestration-service",
    "persona-prompt-service",
    "rag-corpus-service",
    "goals-milestones-service",
    "progress-gamification-service",
    "insight-library-service",
    "feedback-service",
    "research-evaluation-service",
    "voice-service",
    "notification-service",
]

# service -> path (relative to services/<name>/) of its SQLAlchemy engine module.
DB_SERVICES = {
    "auth-user-service": "app/database.py",
    "intake-profiling-service": "app/database.py",
    "goals-milestones-service": "app/database.py",
    "chat-orchestration-service": "app/database.py",
    "rag-corpus-service": "app/db/session.py",
}

REQUIRED_PACKAGES = [
    "prometheus-fastapi-instrumentator==7.0.0",
    "opentelemetry-sdk==1.29.0",
    "opentelemetry-exporter-otlp-proto-grpc==1.29.0",
    "opentelemetry-instrumentation-fastapi==0.50b0",
    "opentelemetry-instrumentation-httpx==0.50b0",
]
DB_PACKAGE = "opentelemetry-instrumentation-sqlalchemy==0.50b0"

FASTAPI_BLOCK_RE = re.compile(r"app = FastAPI\(.*?\n\)\n", re.DOTALL)


def write_observability_module(service: str) -> None:
    path = SERVICES_DIR / service / "app" / "observability.py"
    path.write_text(TEMPLATE, encoding="utf-8")


def patch_main(service: str) -> None:
    main_path = SERVICES_DIR / service / "app" / "main.py"
    text = main_path.read_text(encoding="utf-8")
    if "from .observability import instrument" in text:
        return  # already wired

    match = FASTAPI_BLOCK_RE.search(text)
    if not match:
        raise SystemExit(f"{main_path}: couldn't find `app = FastAPI(...)` block")

    # SERVICE_NAME is defined as a module-level constant in every service's main.py.
    insertion = "\ninstrument(app, SERVICE_NAME)\n"
    text = text[: match.end()] + insertion + text[match.end() :]

    # Add the import: right after the last top-of-file `from fastapi import ...` line
    # (every service imports FastAPI before constructing `app`).
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("from fastapi import"):
            lines.insert(i + 1, "from .observability import instrument")
            break
    else:
        raise SystemExit(f"{main_path}: couldn't find a `from fastapi import` line")

    main_path.write_text("\n".join(lines), encoding="utf-8")


def patch_requirements(service: str) -> None:
    req_path = SERVICES_DIR / service / "requirements.txt"
    text = req_path.read_text(encoding="utf-8")
    packages = list(REQUIRED_PACKAGES)
    if service in DB_SERVICES:
        packages.append(DB_PACKAGE)

    existing_names = {line.split("==")[0] for line in text.splitlines() if line.strip()}
    missing = [p for p in packages if p.split("==")[0] not in existing_names]
    if not missing:
        return
    if not text.endswith("\n"):
        text += "\n"
    text += "\n".join(missing) + "\n"
    req_path.write_text(text, encoding="utf-8")


def patch_db_module(service: str) -> None:
    rel_path = DB_SERVICES.get(service)
    if not rel_path:
        return
    db_path = SERVICES_DIR / service / rel_path
    text = db_path.read_text(encoding="utf-8")
    if "instrument_db(engine)" in text:
        return

    # Import path differs: services/*/app/database.py uses `from .config import ...`
    # (relative); rag-corpus-service/app/db/session.py sits one package level deeper.
    import_line = (
        "from ..observability import instrument_db"
        if rel_path.count("/") > 1
        else "from .observability import instrument_db"
    )

    lines = text.split("\n")
    engine_line_idx = next(
        (i for i, line in enumerate(lines) if line.strip().startswith("engine = create_engine(")),
        None,
    )
    if engine_line_idx is None:
        raise SystemExit(f"{db_path}: couldn't find an `engine = create_engine(...)` line")

    # The create_engine(...) call may span multiple lines; find its closing paren.
    end_idx = engine_line_idx
    depth = lines[engine_line_idx].count("(") - lines[engine_line_idx].count(")")
    while depth > 0:
        end_idx += 1
        depth += lines[end_idx].count("(") - lines[end_idx].count(")")

    lines.insert(end_idx + 1, "instrument_db(engine)")

    # Import: after the last `from ... import` line preceding the engine line.
    last_import_idx = max(
        i for i in range(engine_line_idx) if lines[i].startswith(("from ", "import "))
    )
    lines.insert(last_import_idx + 1, import_line)

    db_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    for service in SERVICES:
        write_observability_module(service)
        patch_main(service)
        patch_requirements(service)
        patch_db_module(service)
        print(f"instrumented {service}")


if __name__ == "__main__":
    main()
