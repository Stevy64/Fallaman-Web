from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    """Journal d'activité plateforme (debug / audit léger)."""

    class Level(models.TextChoices):
        DEBUG = "debug", "Debug"
        INFO = "info", "Info"
        WARNING = "warning", "Attention"
        ERROR = "error", "Erreur"

    class Category(models.TextChoices):
        REQUEST = "request", "Requête"
        AUTH = "auth", "Auth"
        LISTING = "listing", "Annonce"
        PAYMENT = "payment", "Paiement"
        MESSAGING = "messaging", "Messagerie"
        MODERATION = "moderation", "Modération"
        STAFF = "staff", "Équipe"
        SYSTEM = "system", "Système"

    level = models.CharField(max_length=12, choices=Level.choices, default=Level.INFO, db_index=True)
    category = models.CharField(
        max_length=20, choices=Category.choices, default=Category.SYSTEM, db_index=True
    )
    action = models.CharField(max_length=80, db_index=True)
    message = models.TextField(blank=True, default="")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activity_logs",
    )
    path = models.CharField(max_length=400, blank=True, default="")
    method = models.CharField(max_length=10, blank=True, default="")
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at", "level"]),
            models.Index(fields=["category", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.level}] {self.action}"
