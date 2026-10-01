"""Notifications internes.

Volontairement éphémères, pour que la cloche reste lisible : la tâche
``cleanup_notifications`` supprime les non lues de plus de 24 h et les lues de
plus de 3 jours.

L'exception est ``STAFF_BROADCAST`` — les messages de l'équipe. ``is_persistent``
les distingue : ils survivent au nettoyage, sont marqués lus plutôt que
supprimés à l'ouverture, et attendent une suppression explicite du destinataire.
"""

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Notification(models.Model):
    class Kind(models.TextChoices):
        NEW_INTEREST = "new_interest", "Nouvel intérêt"
        NEW_MESSAGE = "new_message", "Nouveau message"
        LISTING_EXPIRING = "listing_expiring", "Annonce bientôt expirée"
        LISTING_EXPIRED = "listing_expired", "Annonce expirée"
        NEW_MATCHING_LISTING = "new_matching_listing", "Nouvelle annonce"
        BOOSTED_LISTING = "boosted_listing", "Annonce mise en avant"
        RECOMMENDED_CANDIDATE = "recommended_candidate", "Candidat recommandé"
        STAFF_NEW_PROFILE = "staff_new_profile", "Nouveau profil"
        STAFF_NEW_LISTING = "staff_new_listing", "Nouvelle annonce (équipe)"
        STAFF_RECOMMENDATION = "staff_recommendation", "Recommandation payante"
        STAFF_BROADCAST = "staff_broadcast", "Message de l'équipe"
        REPORT_STATUS = "report_status", "Signalement"
        SYSTEM = "system", "Système"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="notifications", on_delete=models.CASCADE)
    kind = models.CharField(max_length=40, choices=Kind.choices, default=Kind.SYSTEM)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default="")
    url = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def is_persistent(self) -> bool:
        """Messages équipe : restent jusqu'à suppression explicite."""
        return self.kind == self.Kind.STAFF_BROADCAST

    def get_absolute_url(self):
        return reverse("notifications:open", kwargs={"pk": self.pk})

    def mark_read(self):
        if self.is_read:
            return
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at"])
