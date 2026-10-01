"""
Fichier WSGI pour PythonAnywhere (staging / historique).

Production officielle : OVH Cloud — voir docs/DEPLOIEMENT_OVH.md
(domaine fallaman.gabomazone.com, stack Docker Compose).

À recopier dans l'éditeur WSGI de l'onglet « Web » de PythonAnywhere
(/var/www/<votrecompte>_pythonanywhere_com_wsgi.py), en remplaçant
``<votrecompte>`` partout.

PythonAnywhere ne propage pas les variables d'environnement du shell vers
l'application web : elles sont lues ici depuis le fichier ``.env`` du projet.
"""

import os
import sys
from pathlib import Path

# ── Chemin du projet ────────────────────────────────────────────────────
# Dossier contenant manage.py (sous-dossier Fallaman/ du dépôt).
PROJECT_DIR = Path("/home/<votrecompte>/fallaman-web/Fallaman")
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

# ── Variables d'environnement ───────────────────────────────────────────
# django-environ lit BASE_DIR/.env, mais DJANGO_SETTINGS_MODULE doit être
# connu avant l'import de Django.
env_file = PROJECT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.production"

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
