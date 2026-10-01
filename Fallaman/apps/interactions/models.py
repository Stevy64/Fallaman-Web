"""Manifestations d'intérêt d'un candidat pour une annonce.

Un ``Interest`` est le premier geste : il ouvre la discussion et prévient le
pourvoyeur. La contrainte d'unicité (utilisateur, annonce) évite qu'un candidat
relance dix fois la même annonce.

La création passe par ``services.express_interest()``, qui applique les règles
métier : pas sur sa propre annonce, annonce encore publiée, aucun blocage entre
les deux personnes.
"""

from django.conf import settings
from django.db import models

from apps.listings.models import Listing


class Interest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="interests", on_delete=models.CASCADE)
    listing = models.ForeignKey(Listing, related_name="interests", on_delete=models.CASCADE)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "listing")
        verbose_name = "intérêt"

    def __str__(self):
        return f"{self.user} → {self.listing}"
