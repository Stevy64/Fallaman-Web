from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    CELERY_TASK_ALWAYS_EAGER=(bool, True),
    OTP_CODE_TTL_SECONDS=(int, 300),
    OTP_MAX_ATTEMPTS=(int, 5),
    LISTING_EMPLOYMENT_TTL_DAYS=(int, 30),
    LISTING_MISSION_TTL_DAYS=(int, 7),
    CONVERSATION_IDLE_HOURS=(int, 72),
    CONVERSATION_MAX_DAYS=(int, 7),
)

environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-dev-key-change-me")
DEBUG = env("DJANGO_DEBUG")

# Interrupteur unique des commodités de développement : code OTP fixe, paiement
# simulé, compte équipe de démonstration. Volontairement distinct de DEBUG, que
# le lanceur de tests force à False et qu'on bascule parfois à la main.
DEV_CONVENIENCES = env.bool("DEV_CONVENIENCES", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sitemaps",
    "django_htmx",
    "apps.core",
    "apps.accounts",
    "apps.profiles",
    "apps.taxonomy",
    "apps.locations",
    "apps.listings",
    "apps.interactions",
    "apps.messaging",
    "apps.notifications",
    "apps.moderation",
    "apps.dashboard",
    "apps.payments",
    "apps.recommendations",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "apps.core.middleware.StaffReturnMiddleware",
    "apps.core.middleware.ActivityLogMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.fallaman",
            ],
        },
    }
]

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{(BASE_DIR / 'db.sqlite3').as_posix()}")
}

if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"]["OPTIONS"] = {"timeout": 20}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.PhoneModelBackend"]
# Tous les membres ont un mot de passe depuis le passage à la connexion
# téléphone + mot de passe. 8 caractères : au-delà, sur un clavier de
# téléphone, on pousse surtout les gens à noter leur mot de passe.
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Libreville"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

MEDIA_URL = "/media/"
_media_root = env("MEDIA_ROOT", default="") or str(BASE_DIR / "media")
MEDIA_ROOT = Path(_media_root)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "core:home"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# Plafonds de requête : sans eux, un POST géant sature la mémoire du worker.
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 500

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "fallaman",
    }
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="memory://")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="cache+memory://")
CELERY_TASK_ALWAYS_EAGER = env("CELERY_TASK_ALWAYS_EAGER")
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "expire-listings": {
        "task": "apps.listings.tasks.expire_listings",
        "schedule": 3600.0,
    },
    "expire-conversations": {
        "task": "apps.messaging.tasks.expire_conversations",
        "schedule": 900.0,
    },
    "send-search-alerts": {
        "task": "apps.listings.tasks.send_search_alerts",
        "schedule": 1800.0,
    },
    "cleanup-notifications": {
        "task": "apps.notifications.tasks.cleanup_notifications",
        "schedule": 900.0,
    },
    "notify-profile-matches": {
        "task": "apps.listings.tasks.notify_new_listing_matches",
        "schedule": 1800.0,
    },
    "expire-recommendation-boosts": {
        "task": "apps.recommendations.tasks.expire_recommendation_boosts",
        "schedule": 900.0,
    },
}

# Canal d'envoi du code d'activation : "console" (dev), "email" ou "whatsapp".
# Voir apps/accounts/otp_delivery.py pour en ajouter un.
OTP_PROVIDER = env("OTP_PROVIDER", default="console")
OTP_CODE_TTL_SECONDS = env("OTP_CODE_TTL_SECONDS")
OTP_MAX_ATTEMPTS = env("OTP_MAX_ATTEMPTS")
OTP_DEV_CODE = env("OTP_DEV_CODE", default="123456")

# Envoi des e-mails (code d'activation).
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=15)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Fallaman <no-reply@fallaman.ga>")

# WhatsApp Cloud API (Meta) — canal alternatif, non requis.
WHATSAPP_PHONE_NUMBER_ID = env("WHATSAPP_PHONE_NUMBER_ID", default="")
WHATSAPP_ACCESS_TOKEN = env("WHATSAPP_ACCESS_TOKEN", default="")
WHATSAPP_API_VERSION = env("WHATSAPP_API_VERSION", default="v21.0")
# Nom du modèle approuvé, catégorie « Authentication ».
WHATSAPP_OTP_TEMPLATE = env("WHATSAPP_OTP_TEMPLATE", default="otp_code")
WHATSAPP_OTP_LANGUAGE = env("WHATSAPP_OTP_LANGUAGE", default="fr")
# Les modèles d'authentification Meta portent un bouton « copier le code »
# dont le paramètre doit répéter le code.
WHATSAPP_OTP_HAS_COPY_BUTTON = env.bool("WHATSAPP_OTP_HAS_COPY_BUTTON", default=True)

LISTING_EMPLOYMENT_TTL_DAYS = env("LISTING_EMPLOYMENT_TTL_DAYS")
LISTING_MISSION_TTL_DAYS = env("LISTING_MISSION_TTL_DAYS")
CONVERSATION_IDLE_HOURS = env("CONVERSATION_IDLE_HOURS")
CONVERSATION_MAX_DAYS = env("CONVERSATION_MAX_DAYS")

MAX_LISTING_IMAGES = env.int("MAX_LISTING_IMAGES", default=5)
MAX_UPLOAD_SIZE = env.int("MAX_UPLOAD_SIZE", default=5 * 1024 * 1024)

# À activer uniquement derrière un proxy de confiance (PythonAnywhere, Nginx…),
# sinon X-Forwarded-For devient un moyen trivial de contourner les quotas.
TRUST_PROXY_HEADERS = env.bool("TRUST_PROXY_HEADERS", default=False)
PUBLIC_SITE_NAME = "Fallaman"
PUBLIC_TAGLINE = "Trouvez quelqu'un. Trouvez du travail."

# Boutons de téléchargement de l'app (accueil). Remplacer par les liens stores en prod.
ANDROID_APP_URL = env("ANDROID_APP_URL", default="#")
IOS_APP_URL = env("IOS_APP_URL", default="#")

# Observabilité
SENTRY_DSN = env("SENTRY_DSN", default="")
ACTIVITY_LOG_RETENTION_DAYS = env.int("ACTIVITY_LOG_RETENTION_DAYS", default=30)

# SingPay (recommandations payantes)
SINGPAY_API_KEY = env("SINGPAY_API_KEY", default="")
SINGPAY_API_SECRET = env("SINGPAY_API_SECRET", default="")
SINGPAY_MERCHANT_ID = env("SINGPAY_MERCHANT_ID", default="")
SINGPAY_DISBURSEMENT_ID = env("SINGPAY_DISBURSEMENT_ID", default="")
SINGPAY_ENVIRONMENT = env("SINGPAY_ENVIRONMENT", default="sandbox")
SINGPAY_BASE_URL = env("SINGPAY_BASE_URL", default="")
SINGPAY_LOGO_URL = env("SINGPAY_LOGO_URL", default="")
# Secret de signature des webhooks. À défaut, l'API secret sert de secret HMAC.
SINGPAY_WEBHOOK_SECRET = env("SINGPAY_WEBHOOK_SECRET", default="")
# Fenêtre anti-rejeu sur l'en-tête X-Timestamp.
SINGPAY_WEBHOOK_TOLERANCE_SECONDS = env.int("SINGPAY_WEBHOOK_TOLERANCE_SECONDS", default=300)
# À passer à true une fois le format de X-Timestamp confirmé auprès de SingPay.
SINGPAY_WEBHOOK_REQUIRE_FRESH_TIMESTAMP = env.bool(
    "SINGPAY_WEBHOOK_REQUIRE_FRESH_TIMESTAMP", default=False
)

# Compte équipe de démonstration (développement uniquement).
DEMO_STAFF_PHONE = env("DEMO_STAFF_PHONE", default="+24106111111")
DEMO_STAFF_PASSWORD = env("DEMO_STAFF_PASSWORD", default="")

# Tarification recommandations (FCFA / jour + remises durée)
RECO_LISTING_DAILY_RATE = env.int("RECO_LISTING_DAILY_RATE", default=500)
RECO_PROFILE_DAILY_RATE = env.int("RECO_PROFILE_DAILY_RATE", default=400)
RECO_DURATION_DAYS = [1, 3, 7, 14]
RECO_DURATION_DISCOUNTS = {1: 0, 3: 5, 7: 12, 14: 20}

_LOG_DIR = BASE_DIR / "logs"
_LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
        "verbose": {
            "format": "{levelname} {asctime} {name} {module}:{lineno} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(_LOG_DIR / "fallaman.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "activity_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(_LOG_DIR / "activity.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
    "loggers": {
        "django.security": {"handlers": ["console", "file"], "level": "WARNING", "propagate": False},
        "apps": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "apps.activity": {
            "handlers": ["console", "activity_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Nettoyage journal activité
CELERY_BEAT_SCHEDULE["cleanup-activity-logs"] = {
    "task": "apps.core.tasks.cleanup_activity_logs",
    "schedule": 86400.0,
}
