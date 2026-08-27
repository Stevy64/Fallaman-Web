import time

from django.utils.deprecation import MiddlewareMixin

from apps.core.activity import log_activity
from apps.core.models import ActivityLog

# Chemins ignorés (bruit)
_SKIP_PREFIXES = (
    "/static/",
    "/media/",
    "/favicon",
    "/sw.js",
    "/manifest",
    "/__debug__",
)

# Mutations / zones sensibles toujours journalisées
_HOT_PREFIXES = (
    "/connexion",
    "/paiements/",
    "/publier/",
    "/messages/",
    "/tableau-de-bord/",
    "/annonces/",
    "/profil/",
    "/signaler/",
    "/recommand",
)


class SecurityHeadersMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Referrer-Policy", "same-origin")
        response.setdefault("Permissions-Policy", "geolocation=(self), camera=(), microphone=()")
        if "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = (
                "default-src 'self'; "
                "img-src 'self' data: blob: https:; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' data: https://fonts.gstatic.com; "
                "script-src 'self' 'unsafe-inline'; "
                "connect-src 'self'; "
                "manifest-src 'self'; "
                "worker-src 'self'; "
                "frame-ancestors 'none';"
            )
        return response


class StaffReturnMiddleware(MiddlewareMixin):
    """Mémorise la dernière page dashboard pour un retour depuis le site public."""

    def process_request(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or not getattr(user, "is_staff", False):
            return None
        path = request.path or ""
        if path.startswith("/tableau-de-bord/") and request.method == "GET":
            request.session["staff_return_url"] = request.get_full_path()
        return None


class ActivityLogMiddleware(MiddlewareMixin):
    """Journalise mutations, erreurs HTTP et zones sensibles (sans noyer la DB)."""

    def process_request(self, request):
        request._activity_started = time.perf_counter()
        return None

    def process_response(self, request, response):
        path = getattr(request, "path", "") or ""
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return response

        status = getattr(response, "status_code", 200) or 200
        method = (getattr(request, "method", "") or "GET").upper()
        started = getattr(request, "_activity_started", None)
        duration_ms = int((time.perf_counter() - started) * 1000) if started else None

        is_error = status >= 400
        is_mutation = method in {"POST", "PUT", "PATCH", "DELETE"}
        is_hot = any(path.startswith(p) for p in _HOT_PREFIXES)
        is_slow = duration_ms is not None and duration_ms >= 1500

        if not (is_error or is_mutation or (is_hot and method == "GET" and is_slow) or is_slow):
            return response

        if is_error:
            level = ActivityLog.Level.ERROR if status >= 500 else ActivityLog.Level.WARNING
            category = ActivityLog.Category.REQUEST
            action = f"http.{status}"
        elif is_mutation:
            level = ActivityLog.Level.INFO
            if path.startswith("/tableau-de-bord/"):
                category = ActivityLog.Category.STAFF
            elif path.startswith("/paiements/"):
                category = ActivityLog.Category.PAYMENT
            elif path.startswith("/messages/"):
                category = ActivityLog.Category.MESSAGING
            elif path.startswith("/connexion"):
                category = ActivityLog.Category.AUTH
            else:
                category = ActivityLog.Category.REQUEST
            action = f"{method.lower()}.{path.strip('/').replace('/', '.')[:60] or 'root'}"
        else:
            level = ActivityLog.Level.WARNING if is_slow else ActivityLog.Level.INFO
            category = ActivityLog.Category.REQUEST
            action = "request.slow" if is_slow else "request.hot"

        log_activity(
            action=action,
            message=f"{method} {path} → {status}",
            level=level,
            category=category,
            request=request,
            status_code=status,
            duration_ms=duration_ms,
            extra={"query": (request.META.get("QUERY_STRING") or "")[:200]},
        )
        return response

    def process_exception(self, request, exception):
        log_activity(
            action="exception",
            message=f"{exception.__class__.__name__}: {exception}"[:2000],
            level=ActivityLog.Level.ERROR,
            category=ActivityLog.Category.SYSTEM,
            request=request,
            extra={"exc_type": exception.__class__.__name__},
        )
        return None
