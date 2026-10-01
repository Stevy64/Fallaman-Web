"""Signalements et blocages entre membres.

``BlockedUser`` est dirigé en base (qui bloque qui), mais **symétrique à
l'usage** : ``BlockedUser.objects.is_blocked(a, b)`` est vrai quel que soit le
sens. Un blocage empêche les messages dans les deux directions, y compris à
l'initiative de la personne bloquée.

``Report`` alimente la file de modération du tableau de bord. Le motif est
contraint côté vue à la liste ``Reason`` : Django ne valide pas ``choices`` à
l'enregistrement, une valeur libre y entrerait sinon.
"""

from django.conf import settings
from django.db import models

from apps.listings.models import Listing


class BlockedUserQuerySet(models.QuerySet):
    def is_blocked(self, user_a, user_b) -> bool:
        return self.filter(
            models.Q(blocker=user_a, blocked=user_b) | models.Q(blocker=user_b, blocked=user_a)
        ).exists()


class BlockedUser(models.Model):
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="blocks_made", on_delete=models.CASCADE
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="blocks_received", on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = BlockedUserQuerySet.as_manager()

    class Meta:
        unique_together = ("blocker", "blocked")


class Report(models.Model):
    class Reason(models.TextChoices):
        SCAM = "scam", "Arnaque"
        MONEY_REQUEST = "money_request", "Demande d'argent"
        FAKE_LISTING = "fake_listing", "Fausse annonce"
        SPAM = "spam", "Offre suspecte"
        INAPPROPRIATE = "inappropriate", "Contenu inapproprié"
        ILLEGAL = "illegal", "Contenu illégal"
        OTHER = "other", "Autre"

    class Status(models.TextChoices):
        OPEN = "open", "Ouvert"
        IN_REVIEW = "in_review", "En cours"
        RESOLVED = "resolved", "Traité"
        REJECTED = "rejected", "Rejeté"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="reports_made", on_delete=models.CASCADE
    )
    listing = models.ForeignKey(Listing, null=True, blank=True, related_name="reports", on_delete=models.CASCADE)
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="reports_received",
        on_delete=models.CASCADE,
    )
    reason = models.CharField(max_length=32, choices=Reason.choices)
    details = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "signalement"

    def __str__(self):
        return f"{self.get_reason_display()} #{self.pk}"
