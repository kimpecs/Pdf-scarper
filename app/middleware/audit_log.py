"""
Audit log middleware for Larry — LIG Parts Intelligence.

Records every mutating HTTP request (POST, PUT, PATCH, DELETE) to the
audit_log table.  Read-only requests (GET, HEAD, OPTIONS) are skipped.

Governance requirement: all data mutations must leave an immutable trail.
No auto-approve, no silent writes.
"""

import json
import time
from datetime import datetime, timezone

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# Lazy import so the app still boots if SQLAlchemy isn't wired yet
_session_factory = None


def set_session_factory(factory):
    """Call this from main.py after the SQLAlchemy engine is created."""
    global _session_factory
    _session_factory = factory


MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
MAX_BODY_BYTES   = 4096   # truncate large bodies before storing


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Starlette/FastAPI middleware that writes one AuditLog row per
    mutating request.  Failures to write are logged but never raise —
    the original response is always returned to the client.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in MUTATING_METHODS:
            return await call_next(request)

        # Read body (must be consumed before call_next or body is lost)
        body_bytes = await request.body()
        body_snippet = body_bytes[:MAX_BODY_BYTES].decode("utf-8", errors="replace") if body_bytes else None

        start = time.monotonic()
        response: Response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000

        # Fire-and-forget write to audit_log
        try:
            await self._write_log(request, response.status_code, body_snippet, duration_ms)
        except Exception as exc:
            # Never let audit failure break the response
            import logging
            logging.getLogger("larry.audit").error("Audit write failed: %s", exc)

        return response

    async def _write_log(
        self,
        request: Request,
        status_code: int,
        request_body: str | None,
        duration_ms: float,
    ):
        if _session_factory is None:
            return  # SQLAlchemy not yet configured — skip silently

        # Import here to avoid circular imports at module load time
        from app.services.db.orm_models import AuditLog

        ip = request.client.host if request.client else None

        row = AuditLog(
            timestamp    = datetime.now(timezone.utc),
            method       = request.method,
            path         = str(request.url.path),
            status_code  = status_code,
            user_agent   = request.headers.get("user-agent"),
            ip_address   = ip,
            request_body = request_body,
            duration_ms  = round(duration_ms, 2),
            actor        = request.headers.get("x-actor"),   # future auth header
        )

        with _session_factory() as session:
            session.add(row)
            session.commit()
