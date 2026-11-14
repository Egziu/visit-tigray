"""Visit Tigray API — modular monolith entry point."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.core.security import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from app.modules import registry

log = logging.getLogger("visit_tigray")


def create_app() -> FastAPI:
    s = get_settings()
    configure_logging()
    problems = s.validate_for_production()
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
    app = FastAPI(
        title="Visit Tigray API",
        version="2.0.0-dev",
        description="Visit Tigray — Discover. Experience. Remember. Pre-release; not an official government service.",
        docs_url="/api/docs" if s.expose_api_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if s.expose_api_docs else None,
    )
    install_error_handlers(app)
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=s.allowed_hosts)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                       allow_headers=["content-type", "x-csrf-token", "authorization", "x-request-id"])
    for router in registry.routers():
        app.include_router(router)
    return app


app = create_app()
