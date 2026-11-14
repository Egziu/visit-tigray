"""OpenID Connect (authorization code + PKCE) for staff single sign-on, e.g. Keycloak.

Keycloak (or any compliant IdP) remains responsible for MFA policy when OIDC is used. If the
ID token's ``amr``/``acr`` claims indicate multi-factor authentication, the session is marked
``mfa_verified``. Otherwise staff must still complete local TOTP.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.egress import guarded_client
from app.core.errors import AppError
from app.modules.identity.models import OidcLoginState

_cache: dict[str, Any] = {}
MFA_AMR = {"mfa", "otp", "hwk", "swk", "totp", "webauthn"}


def _enabled() -> None:
    s = get_settings()
    if not (s.oidc_issuer and s.oidc_client_id and s.oidc_redirect_uri):
        raise AppError(503, "oidc_not_configured", "Single sign-on is not configured for this deployment.")


def discovery(http=None) -> dict:
    s = get_settings()
    issuer = s.oidc_issuer or ""
    key = f"disc:{issuer}"
    if key not in _cache or _cache[key][1] < time.time():
        with (http or guarded_client("oidc", "cloud_assisted", timeout=10)) as c:
            doc = c.get(issuer.rstrip("/") + "/.well-known/openid-configuration").json()
        if doc.get("issuer") != s.oidc_issuer:
            raise AppError(502, "oidc_issuer_mismatch", "Identity provider issuer mismatch.")
        _cache[key] = (doc, time.time() + 3600)
    return _cache[key][0]


def jwks(http=None) -> dict:
    key = "jwks"
    if key not in _cache or _cache[key][1] < time.time():
        with (http or guarded_client("oidc", "cloud_assisted", timeout=10)) as c:
            _cache[key] = (c.get(discovery(http)["jwks_uri"]).json(), time.time() + 3600)
    return _cache[key][0]


def start_login(db: Session, http=None) -> str:
    _enabled()
    s = get_settings()
    state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    db.add(OidcLoginState(state=state, nonce=nonce, code_verifier=verifier))
    db.flush()
    params = {"response_type": "code", "client_id": s.oidc_client_id, "redirect_uri": s.oidc_redirect_uri,
              "scope": "openid email profile", "state": state, "nonce": nonce, "code_challenge": challenge,
              "code_challenge_method": "S256"}
    return discovery(http)["authorization_endpoint"] + "?" + urlencode(params)


def validate_id_token(id_token: str, nonce: str, jwk_set: dict) -> dict:
    """Verify signature (RS256/ES256 from JWKS), issuer, audience, expiry and nonce."""
    s = get_settings()
    try:
        header = jwt.get_unverified_header(id_token)
        keys = {k["kid"]: k for k in jwk_set.get("keys", []) if "kid" in k}
        jwk = keys.get(header.get("kid"))
        if jwk is None or header.get("alg") not in ("RS256", "ES256", "PS256"):
            raise AppError(401, "oidc_invalid_token", "Unknown signing key or algorithm.")
        key = jwt.PyJWK(jwk).key
        claims = jwt.decode(id_token, key=key, algorithms=[header["alg"]], audience=s.oidc_client_id,
                            issuer=s.oidc_issuer, options={"require": ["exp", "iat", "sub", "aud", "iss"]})
    except jwt.PyJWTError as exc:
        raise AppError(401, "oidc_invalid_token", f"ID token rejected: {exc}") from exc
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise AppError(401, "oidc_invalid_token", "Nonce mismatch.")
    return claims


def complete_login(db: Session, code: str, state: str, http=None) -> dict:
    _enabled()
    s = get_settings()
    st = db.get(OidcLoginState, state)
    if st is None or (time.time() - st.created_at.timestamp()) > 600:
        raise AppError(400, "oidc_bad_state", "Login session expired. Please try again.")
    db.delete(st)
    with (http or guarded_client("oidc", "cloud_assisted", timeout=15)) as c:
        tok = c.post(discovery(http)["token_endpoint"], data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": s.oidc_redirect_uri,
            "client_id": s.oidc_client_id, "client_secret": s.oidc_client_secret or "", "code_verifier": st.code_verifier,
        }).json()
    if "id_token" not in tok:
        raise AppError(401, "oidc_exchange_failed", "Identity provider did not return an ID token.")
    claims = validate_id_token(tok["id_token"], st.nonce, jwks(http))
    claims["_mfa"] = bool(set(claims.get("amr", []) or []) & MFA_AMR)
    return claims
