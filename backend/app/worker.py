"""Background worker: durable jobs, scheduled publication and retention sweeps.

Run: python -m app.worker   (several workers may run; job claiming uses SKIP LOCKED)
"""
from __future__ import annotations

import logging
import signal
import time
from datetime import timedelta

from sqlalchemy import delete

from app.core.db import session_factory, utcnow
from app.core.logging import configure_logging
from app.modules.registry import load_models

log = logging.getLogger("visit_tigray.worker")
_running = True


def periodic(db) -> dict:
    """Housekeeping that must run even if no jobs are queued."""
    from app.modules.content.service import publish_due
    from app.modules.identity.models import OidcLoginState, UserSession
    from app.modules.tie.models import Conversation

    published = publish_due(db)
    expired_conv = db.execute(delete(Conversation).where(Conversation.expires_at < utcnow())).rowcount
    expired_sessions = db.execute(delete(UserSession).where(UserSession.expires_at < utcnow())).rowcount
    db.execute(delete(OidcLoginState).where(OidcLoginState.created_at < utcnow() - timedelta(hours=1)))
    db.commit()
    return {"published": published, "expired_conversations": expired_conv, "expired_sessions": expired_sessions}


def main() -> None:  # pragma: no cover - long-running process
    configure_logging()
    load_models()
    from app.modules.platform.service import run_due_jobs

    def stop(*_):
        global _running
        _running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    last_periodic = 0.0
    while _running:
        db = session_factory()()
        try:
            n = run_due_jobs(db)
            if time.time() - last_periodic > 60:
                log.info("periodic %s", periodic(db))
                last_periodic = time.time()
            if n:
                log.info("ran %d jobs", n)
        except Exception:  # noqa: BLE001
            log.exception("worker iteration failed")
            db.rollback()
        finally:
            db.close()
        time.sleep(2)


if __name__ == "__main__":  # pragma: no cover
    main()
