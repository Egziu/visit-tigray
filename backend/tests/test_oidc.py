"""OIDC (Keycloak-compatible) login: ID-token validation and the full callback flow against a mock IdP."""
from __future__ import annotations

import json
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.identity import oidc

ISSUER = "https://idp.example.test/realms/visit-tigray"
CLIENT = "visit-tigray-web"


@pytest.fixture
def keys():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update({"kid": "k1", "use": "sig", "alg": "RS256"})
    return key, {"keys": [jwk]}


@pytest.fixture
def oidc_settings(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "oidc_issuer", ISSUER)
    monkeypatch.setattr(s, "oidc_client_id", CLIENT)
    monkeypatch.setattr(s, "oidc_client_secret", "test-secret")
    monkeypatch.setattr(s, "oidc_redirect_uri", "http://localhost:3000/api/auth/oidc/callback")
    oidc._cache.clear()
    yield s
    oidc._cache.clear()


def token(key, **over):
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": CLIENT, "sub": "kc-user-1", "iat": now, "exp": now + 300, "nonce": "n1",
              "email": "officer@example.test", "email_verified": True, "name": "Officer", "amr": ["pwd", "otp"]}
    claims.update(over)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": over.pop("_kid", "k1")})


def test_valid_token_accepted(keys, oidc_settings):
    key, jwks = keys
    claims = oidc.validate_id_token(token(key), "n1", jwks)
    assert claims["sub"] == "kc-user-1"


@pytest.mark.parametrize("over,nonce", [
    ({"nonce": "other"}, "n1"),                     # replayed / mismatched nonce
    ({"aud": "someone-else"}, "n1"),                # wrong audience
    ({"iss": "https://evil.example.test"}, "n1"),   # wrong issuer
    ({"exp": int(time.time()) - 10}, "n1"),         # expired
])
def test_invalid_claims_rejected(keys, oidc_settings, over, nonce):
    key, jwks = keys
    with pytest.raises(AppError) as e:
        oidc.validate_id_token(token(key, **over), nonce, jwks)
    assert e.value.code == "oidc_invalid_token"


def test_wrong_key_unknown_kid_and_alg_confusion_rejected(keys, oidc_settings):
    key, jwks = keys
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(AppError):
        oidc.validate_id_token(token(other), "n1", jwks)  # signature by a different key
    bad_kid = jwt.encode({"iss": ISSUER, "aud": CLIENT, "sub": "x", "iat": 1, "exp": 9999999999, "nonce": "n1"}, key,
                         algorithm="RS256", headers={"kid": "nope"})
    with pytest.raises(AppError):
        oidc.validate_id_token(bad_kid, "n1", jwks)
    hs = jwt.encode({"iss": ISSUER, "aud": CLIENT, "sub": "x", "iat": 1, "exp": 9999999999, "nonce": "n1"},
                    "symmetric-secret-key-of-32-bytes!!", algorithm="HS256", headers={"kid": "k1"})
    with pytest.raises(AppError):
        oidc.validate_id_token(hs, "n1", jwks)  # HS256 forged with a guessable secret must fail


def test_full_login_flow_with_mock_idp(keys, oidc_settings, client, db, monkeypatch):
    key, jwks = keys
    state_holder = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(200, json={"issuer": ISSUER, "authorization_endpoint": ISSUER + "/auth",
                                             "token_endpoint": ISSUER + "/token", "jwks_uri": ISSUER + "/certs"})
        if path.endswith("/certs"):
            return httpx.Response(200, json=jwks)
        if path.endswith("/token"):
            form = parse_qs(request.content.decode())
            assert form["code_verifier"][0] and form["grant_type"] == ["authorization_code"]  # PKCE used
            return httpx.Response(200, json={"id_token": token(key, nonce=state_holder["nonce"])})
        return httpx.Response(404)

    from app.core import egress
    real = egress.guarded_client
    monkeypatch.setattr(oidc, "guarded_client", lambda purpose, mode, timeout=30.0: real(
        purpose, mode, timeout, transport=httpx.MockTransport(handler)))
    r = client.get("/api/auth/oidc/login")
    q = parse_qs(urlsplit(r.json()["redirect_url"]).query)
    assert q["code_challenge_method"] == ["S256"] and q["client_id"] == [CLIENT]
    state_holder["nonce"] = q["nonce"][0]
    cb = client.get("/api/auth/oidc/callback", params={"code": "abc", "state": q["state"][0]}, follow_redirects=False)
    assert cb.status_code == 303 and "vt_session" in cb.headers["set-cookie"]
    me = client.get("/api/me").json()
    assert me["email"] == "officer@example.test" and me["mfa_verified"] is True  # amr contained otp
    # state is single-use (replay rejected)
    again = client.get("/api/auth/oidc/callback", params={"code": "abc", "state": q["state"][0]})
    assert again.json()["error"]["code"] == "oidc_bad_state"


def test_oidc_disabled_when_unconfigured(client):
    r = client.get("/api/auth/oidc/login")
    assert r.status_code == 503 and r.json()["error"]["code"] == "oidc_not_configured"
