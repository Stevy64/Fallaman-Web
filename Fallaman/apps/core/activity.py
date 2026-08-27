import logging
from typing import Any

from django.db import IntegrityError, OperationalError

from .models import ActivityLog

logger = logging.getLogger("apps.activity")


def client_ip(request) -> str | None:
    if request is None:
        return None
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return forwarded or request.META.get("REMOTE_ADDR") or None


def log_activity(
    *,
    action: str,
    message: str = "",
    level: str = ActivityLog.Level.INFO,
    category: str = ActivityLog.Category.SYSTEM,
    user=None,
    request=None,
    status_code: int | None = None,
    duration_ms: int | None = None,
    extra: dict[str, Any] | None = None,
) -> ActivityLog | None:
    """Enregistre une activité plateforme (best-effort, jamais bloquant)."""
    path = ""
    method = ""
    ip = None
    if request is not None:
        path = (getattr(request, "path", "") or "")[:400]
        method = (getattr(request, "method", "") or "")[:10]
        ip = client_ip(request)
        if user is None:
            u = getattr(request, "user", None)
            if u is not None and getattr(u, "is_authenticated", False):
                user = u

    payload = {
        "level": level,
        "category": category,
        "action": (action or "unknown")[:80],
        "message": (message or "")[:2000],
        "user": user if getattr(user, "pk", None) else None,
        "path": path,
        "method": method,
        "status_code": status_code,
        "ip_address": ip,
        "duration_ms": duration_ms,
        "extra": extra or {},
    }
    try:
        return ActivityLog.objects.create(**payload)
    except (OperationalError, IntegrityError) as exc:
        logger.warning("activity log write failed: %s", exc)
        return None
    except Exception:
        logger.exception("activity log unexpected failure")
        return None
