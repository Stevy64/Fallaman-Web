import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class PaymentTransaction(models.Model):
    class Provider(models.TextChoices):
        SINGPAY = "singpay", "SingPay"
        MOCK = "mock", "Simulation"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        SUCCESS = "success", "Payé"
        FAILED = "failed", "Échoué"
        CANCELLED = "cancelled", "Annulé"

    class Purpose(models.TextChoices):
        LISTING_BOOST = "listing_boost", "Boost annonce"
        PROFILE_BOOST = "profile_boost", "Recommandation profil"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="payment_transactions",
        on_delete=models.CASCADE,
    )
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.SINGPAY)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    amount = models.PositiveIntegerField(help_text="Montant en FCFA")
    # Le Gabon est en zone CEMAC : franc CFA d'Afrique centrale (XAF), pas XOF.
    currency = models.CharField(max_length=8, default="XAF")
    description = models.CharField(max_length=255, blank=True)
    reference = models.CharField(max_length=120, unique=True, db_index=True)
    provider_transaction_id = models.CharField(max_length=120, blank=True, db_index=True)
    payment_url = models.URLField(blank=True, max_length=500)
    metadata = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["purpose", "status"]),
        ]

    def __str__(self):
        return f"{self.reference} · {self.amount} FCFA · {self.status}"

    def mark_success(self, provider_transaction_id: str = ""):
        if self.status == self.Status.SUCCESS:
            return False
        self.status = self.Status.SUCCESS
        self.paid_at = timezone.now()
        if provider_transaction_id:
            self.provider_transaction_id = provider_transaction_id
        self.save(
            update_fields=[
                "status",
                "paid_at",
                "provider_transaction_id",
                "updated_at",
            ]
        )
        return True

    def mark_failed(self):
        if self.status == self.Status.SUCCESS:
            return False
        self.status = self.Status.FAILED
        self.save(update_fields=["status", "updated_at"])
        return True


class SingPayWebhookLog(models.Model):
    payload = models.JSONField(default=dict)
    headers = models.JSONField(default=dict)
    signature_valid = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
