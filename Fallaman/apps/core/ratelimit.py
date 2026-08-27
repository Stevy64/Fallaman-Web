import hashlib
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseForbidden


def client_ip(request) -> str:
    """
    IP réelle du client.

    Derrière le proxy PythonAnywhere, ``REMOTE_ADDR`` vaut l'adresse du proxy :
    tous les visiteurs partageraient alors le même compteur. On lit donc
    ``X-Forwarded-For``, mais uniquement quand le déploiement déclare tourner
    derrière un proxy de confiance — sinon l'en-tête, librement falsifiable,
    permettrait de réinitialiser son quota à volonté.
    """
    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            # Le client d'origine est en tête de liste.
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "anon"


def _identity(request) -> str:
    if request.user.is_authenticated:
        return f"u{request.user.pk}"
    # Haché : évite de stocker des IP en clair dans le cache.
    return "ip" + hashlib.sha256(client_ip(request).encode()).hexdigest()[:16]


#: Méthodes sans effet de bord : les compter reviendrait à bloquer quelqu'un
#: qui se contente de rafraîchir le formulaire de connexion.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def rate_limit(key_prefix: str, limit: int, window_seconds: int):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.method in SAFE_METHODS:
                return view_func(request, *args, **kwargs)

            cache_key = f"rl:{key_prefix}:{_identity(request)}"
            # `add` ne pose la clé que si elle est absente : c'est lui qui fixe
            # la fenêtre, pour qu'elle ne soit pas repoussée à chaque requête.
            if cache.add(cache_key, 1, window_seconds):
                count = 1
            else:
                try:
                    count = cache.incr(cache_key)
                except ValueError:
                    # La clé a expiré entre le `add` et le `incr`.
                    cache.set(cache_key, 1, window_seconds)
                    count = 1
            if count > limit:
                return HttpResponseForbidden("Trop de tentatives. Réessayez plus tard.")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
