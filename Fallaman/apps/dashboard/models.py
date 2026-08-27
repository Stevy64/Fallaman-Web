from django.conf import settings
from django.db import models


class StaffBroadcast(models.Model):
    """Message envoyé par l'équipe à tous les utilisateurs (ou un ciblage simple)."""

    class Audience(models.TextChoices):
        ALL = "all", "Tous les membres"
        ACTIVE = "active", "Comptes actifs uniquement"
        ONE = "one", "Une seule personne"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="staff_broadcasts",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=160)
    body = models.TextField(max_length=2000)
    audience = models.CharField(max_length=20, choices=Audience.choices, default=Audience.ACTIVE)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="received_staff_broadcasts",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    recipient_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.recipient_count})"
