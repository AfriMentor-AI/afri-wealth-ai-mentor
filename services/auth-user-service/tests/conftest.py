"""Test fixtures.

Set DATABASE_URL to a temp SQLite file *before* importing the app, so the engine binds
to it. Tables are recreated fresh for each test for isolation. No module reloads (that
would re-register ORM classes on the declarative base).
"""
import os
import tempfile

import pytest

# Must run before `app.*` is imported anywhere.
_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_TMP.name}"
os.environ["APP_ENV"] = "test"


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.database import Base, engine
    from app.main import app

    # Fresh schema per test.
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as c:
        yield c


def pytest_sessionfinish(session, exitstatus):
    try:
        os.unlink(_TMP.name)
    except OSError:
        pass
