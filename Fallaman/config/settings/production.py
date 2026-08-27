from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import SENTRY_DSN, env

DEBUG = False
# Aucune commodité de développement ne survit en production.
DEV_CONVENIENCES = False
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS")

SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
SECURE_HSTS_SECONDS = 31536000 if SECURE_SSL_REDIRECT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_SSL_REDIRECT
SECURE_HSTS_PRELOAD = SECURE_SSL_REDIRECT
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CELERY_TASK_ALWAYS_EAGER = False

# ── Garde-fous de démarrage ─────────────────────────────────────────────
# Chacune de ces configurations est exploitable telle quelle en production.
# Mieux vaut un déploiement qui refuse de démarrer qu'un site ouvert.

if SECRET_KEY in {"", "unsafe-dev-key-change-me", "change-me-in-production"}:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY doit être une valeur secrète et unique en production."
    )

if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS doit lister explicitement vos domaines (jamais '*')."
    )

# OTP_PROVIDER=console fige le code à OTP_DEV_CODE : n'importe qui se connecte
# alors sur n'importe quel numéro avec « 123456 ».
_otp_provider = env("OTP_PROVIDER", default="console")
if _otp_provider == "console":
    raise ImproperlyConfigured(
        "OTP_PROVIDER=console est un contournement d'authentification en production. "
        "Configurez un canal d'envoi réel (par ex. email)."
    )
if _otp_provider == "email" and not env("EMAIL_HOST", default=""):
    # Sinon personne ne reçoit son code : le site est en ligne mais inaccessible.
    raise ImproperlyConfigured(
        "OTP_PROVIDER=email exige EMAIL_HOST (et les identifiants SMTP associés)."
    )
if _otp_provider == "whatsapp" and not (
    env("WHATSAPP_PHONE_NUMBER_ID", default="") and env("WHATSAPP_ACCESS_TOKEN", default="")
):
    raise ImproperlyConfigured(
        "OTP_PROVIDER=whatsapp exige WHATSAPP_PHONE_NUMBER_ID et WHATSAPP_ACCESS_TOKEN."
    )

# Le paiement simulé crédite les recommandations sans encaisser.
if env.bool("SINGPAY_MOCK", default=False):
    raise ImproperlyConfigured("SINGPAY_MOCK ne doit jamais être activé en production.")

if env("DEMO_STAFF_PASSWORD", default=""):
    raise ImproperlyConfigured(
        "DEMO_STAFF_PASSWORD ne doit pas être défini en production : ce compte "
        "de démonstration est administrateur."
    )

# ── Cache ───────────────────────────────────────────────────────────────
# LocMemCache est propre à chaque worker : les compteurs de limitation de débit
# y sont donc divisés par le nombre de processus, et remis à zéro à chaque
# redémarrage. En production il faut un cache partagé.
_redis_url = env("REDIS_URL", default="")
if _redis_url:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _redis_url,
        }
    }
else:
    # Sans Redis (cas PythonAnywhere), le cache table fait l'affaire.
    # À créer une fois : python manage.py createcachetable
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "fallaman_cache",
        }
    }

# Sans broker joignable, `.delay()` bloque puis échoue : on exécute en direct.
if not env("CELERY_BROKER_URL", default=""):
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = False

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.1),
        send_default_pii=False,
        environment=env("SENTRY_ENVIRONMENT", default="production"),
    )
