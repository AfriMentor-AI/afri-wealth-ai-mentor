"""Gateway test fixtures.

Generate an ephemeral RSA keypair, hand the gateway the public key via env (so no JWKS
network fetch is needed), and expose a token factory for signing access/refresh tokens.
"""
import datetime as dt
import os

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PRIVATE_PEM = _KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
_PUBLIC_PEM = _KEY.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode()

os.environ["JWT_PUBLIC_KEY"] = _PUBLIC_PEM
os.environ["APP_ENV"] = "test"


def make_token(sub="user-1", roles=None, token_type="access", expired=False):
    now = dt.datetime.now(tz=dt.UTC)
    exp = now - dt.timedelta(minutes=5) if expired else now + dt.timedelta(minutes=15)
    payload = {
        "sub": sub,
        "roles": roles or ["user"],
        "type": token_type,
        "iss": "afrimentor-auth",
        "iat": now,
        "exp": exp,
    }
    return jwt.encode(payload, _PRIVATE_PEM, algorithm="RS256")


@pytest.fixture()
def token_factory():
    return make_token


@pytest.fixture()
def client(monkeypatch):
    from app import auth, ratelimit
    from app.main import app

    auth.reset_key_cache()
    ratelimit.reset_local()

    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c
