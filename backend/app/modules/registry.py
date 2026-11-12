"""Module registry: the single place where bounded contexts are wired into the app.

Importing each module's ``models`` here also makes Alembic autogenerate see every table.
"""
from __future__ import annotations

import importlib

MODULES = [
    "identity", "audit", "platform", "content", "media", "knowledge", "tie", "planner",
]


def load_models() -> None:
    for m in MODULES:
        try:
            importlib.import_module(f"app.modules.{m}.models")
        except ModuleNotFoundError as e:
            if e.name != f"app.modules.{m}.models":
                raise


def routers():
    load_models()
    out = []
    for m in MODULES:
        try:
            mod = importlib.import_module(f"app.modules.{m}.router")
        except ModuleNotFoundError as e:
            if e.name != f"app.modules.{m}.router":
                raise
            continue
        out.append(mod.router)
        for extra in ("admin_router", "public_router"):
            if hasattr(mod, extra):
                out.append(getattr(mod, extra))
    return out
