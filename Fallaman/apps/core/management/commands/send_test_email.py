"""Vérifie la configuration d'envoi d'e-mails sans passer par l'inscription.

Utile en production : c'est le moyen le plus court de savoir si le relais SMTP
répond, avant de découvrir le problème parce qu'un membre ne reçoit pas son
code d'activation.

    python manage.py send_test_email vous@exemple.com
"""

from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Envoie un e-mail de test à l'adresse indiquée."

    def add_arguments(self, parser):
        parser.add_argument("destinataire", help="Adresse qui recevra l'e-mail de test.")

    def handle(self, *args, **options):
        destinataire = options["destinataire"]

        self.stdout.write("Configuration active :")
        for nom in (
            "OTP_PROVIDER",
            "EMAIL_BACKEND",
            "EMAIL_HOST",
            "EMAIL_PORT",
            "EMAIL_USE_TLS",
            "EMAIL_USE_SSL",
            "DEFAULT_FROM_EMAIL",
        ):
            self.stdout.write(f"  {nom:<20} = {getattr(settings, nom, '(absent)')}")
        # Le mot de passe n'est jamais affiché, seulement sa présence.
        renseigne = "oui" if getattr(settings, "EMAIL_HOST_PASSWORD", "") else "non"
        self.stdout.write(f"  {'EMAIL_HOST_PASSWORD':<20} = (renseigné : {renseigne})")
        self.stdout.write("")

        try:
            envoyes = send_mail(
                subject="Test de configuration Fallaman",
                message=(
                    "Cet e-mail confirme que l'envoi fonctionne.\n\n"
                    "Les codes d'activation des nouveaux comptes emprunteront "
                    "exactement ce chemin.\n\n— Fallaman"
                ),
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "") or None,
                recipient_list=[destinataire],
                fail_silently=False,
            )
        except Exception as exc:
            raise CommandError(
                f"Échec de l'envoi : {exc.__class__.__name__} : {exc}"
            ) from exc

        if not envoyes:
            raise CommandError("Le relais n'a accepté aucun message.")
        self.stdout.write(self.style.SUCCESS(f"E-mail envoyé à {destinataire}."))
