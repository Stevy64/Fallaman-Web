from .base import *  # noqa: F403
from .base import env

DEBUG = True
ALLOWED_HOSTS = ["*"]
# Code OTP fixe, paiement simulé, compte équipe de démonstration.
DEV_CONVENIENCES = env.bool("DEV_CONVENIENCES", default=True)
# Console par défaut, mais surchargeable : c'est ce qui permet de tester le
# vrai chemin SMTP en local (Mailpit, ou un relais réel).
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=True)
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Compte équipe de démonstration : ce mot de passe n'existe qu'en développement.
# `ensure_demo_staff_user()` refuse de s'exécuter dès que DEV_CONVENIENCES est faux.
DEMO_STAFF_PASSWORD = env("DEMO_STAFF_PASSWORD", default="FallamanAdmin2026!")
