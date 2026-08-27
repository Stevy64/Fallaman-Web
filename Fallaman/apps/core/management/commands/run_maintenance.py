"""Exécute les tâches périodiques sans Celery beat.

PythonAnywhere ne fait pas tourner de worker Celery : sans cette commande,
les annonces n'expirent jamais, les conversations ne se purgent pas et les
recommandations payantes restent actives indéfiniment après leur échéance.

À brancher sur les « Scheduled tasks » de PythonAnywhere :

    cd ~/Fallaman && .venv/bin/python manage.py run_maintenance --hourly
    cd ~/Fallaman && .venv/bin/python manage.py run_maintenance --daily
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger("apps.core")


def _expire_listings():
    from apps.listings.tasks import expire_listings

    return expire_listings()


def _expire_conversations():
    from apps.messaging.tasks import expire_conversations

    return expire_conversations()


def _send_search_alerts():
    from apps.listings.tasks import send_search_alerts

    return send_search_alerts()


def _cleanup_notifications():
    from apps.notifications.tasks import cleanup_notifications

    return cleanup_notifications()


def _notify_new_listing_matches():
    from apps.listings.tasks import notify_new_listing_matches

    return notify_new_listing_matches()


def _expire_recommendation_boosts():
    from apps.recommendations.tasks import expire_recommendation_boosts

    return expire_recommendation_boosts()


def _cleanup_activity_logs():
    from apps.core.tasks import cleanup_activity_logs

    return cleanup_activity_logs()


#: Tâches fréquentes : expiration et diffusion.
HOURLY = [
    ("expire_listings", _expire_listings),
    ("expire_conversations", _expire_conversations),
    ("expire_recommendation_boosts", _expire_recommendation_boosts),
    ("send_search_alerts", _send_search_alerts),
    ("notify_new_listing_matches", _notify_new_listing_matches),
    ("cleanup_notifications", _cleanup_notifications),
]

#: Tâches de nettoyage lourdes.
DAILY = [
    ("cleanup_activity_logs", _cleanup_activity_logs),
]


class Command(BaseCommand):
    help = "Exécute les tâches de maintenance périodiques (remplace Celery beat)."

    def add_arguments(self, parser):
        parser.add_argument("--hourly", action="store_true", help="Tâches horaires.")
        parser.add_argument("--daily", action="store_true", help="Tâches quotidiennes.")
        parser.add_argument(
            "--task",
            help="Exécute une seule tâche par son nom.",
        )

    def handle(self, *args, **options):
        if options["task"]:
            registry = dict(HOURLY + DAILY)
            if options["task"] not in registry:
                self.stderr.write(f"Tâche inconnue : {options['task']}")
                self.stderr.write(f"Disponibles : {', '.join(sorted(registry))}")
                return
            jobs = [(options["task"], registry[options["task"]])]
        elif options["daily"]:
            jobs = DAILY
        elif options["hourly"]:
            jobs = HOURLY
        else:
            jobs = HOURLY + DAILY

        for name, job in jobs:
            # Une tâche qui échoue ne doit pas empêcher les suivantes de tourner.
            try:
                result = job()
            except Exception:
                logger.exception("Maintenance : échec de %s", name)
                self.stderr.write(self.style.ERROR(f"{name} : échec (voir les logs)"))
                continue
            self.stdout.write(self.style.SUCCESS(f"{name} : {result}"))
