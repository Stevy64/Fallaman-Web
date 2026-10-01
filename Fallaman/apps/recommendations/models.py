"""Recommandations payantes : mise en avant d'une annonce ou d'un profil.

``RecommendationPurchase`` relie un paiement à la prestation vendue. Le cycle
est : ``PENDING`` à la création → ``ACTIVE`` une fois le paiement confirmé
(``services.activate_purchase``) → ``EXPIRED`` par la tâche périodique.

L'activation est **cumulative** : acheter alors qu'une mise en avant court
encore prolonge à partir de son échéance, sans perdre le temps déjà payé.

``CandidateIntroduction`` est l'autre versant : un profil recommandé est proposé
à un pourvoyeur. La discussion n'est ouverte qu'après acceptation explicite
(``can_contact``) — un candidat payant ne peut pas écrire d'office.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class RecommendationPurchase(models.Model):
    """Achat optionnel de visibilité (annonce ou profil demandeur)."""

    class Kind(models.TextChoices):
        LISTING = "listing", "Boost annonce"
        PROFILE = "profile", "Recommandation profil"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente de paiement"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expirée"
        CANCELLED = "cancelled", "Annulée"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="recommendation_purchases",
        on_delete=models.CASCADE,
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    listing = models.ForeignKey(
        "listings.Listing",
        null=True,
        blank=True,
        related_name="recommendation_purchases",
        on_delete=models.CASCADE,
    )
    profile = models.ForeignKey(
        "profiles.Profile",
        null=True,
        blank=True,
        related_name="recommendation_purchases",
        on_delete=models.CASCADE,
    )
    payment = models.OneToOneField(
        "payments.PaymentTransaction",
        null=True,
        blank=True,
        related_name="recommendation_purchase",
        on_delete=models.SET_NULL,
    )
    duration_days = models.PositiveSmallIntegerField()
    amount = models.PositiveIntegerField(help_text="Montant FCFA")
    daily_rate = models.PositiveIntegerField(help_text="Tarif journalier appliqué")
    discount_percent = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True, db_index=True)
    score = models.PositiveIntegerField(default=0, help_text="Poids de ranking")
    notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["kind", "status", "ends_at"]),
            models.Index(fields=["status", "ends_at"]),
        ]

    def __str__(self):
        target = self.listing_id or self.profile_id
        return f"{self.get_kind_display()} #{target} · {self.duration_days}j · {self.status}"

    @property
    def is_live(self) -> bool:
        now = timezone.now()
        return (
            self.status == self.Status.ACTIVE
            and self.ends_at is not None
            and self.ends_at > now
        )

    def remaining_hours(self) -> int:
        if not self.ends_at:
            return 0
        delta = self.ends_at - timezone.now()
        return max(0, int(delta.total_seconds() // 3600))


class CandidateIntroduction(models.Model):
    """
    Mise en relation : un profil recommandé est proposé à un pourvoyeur.
    Discussion / WhatsApp uniquement après acceptation.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        ACCEPTED = "accepted", "Accepté"
        DECLINED = "declined", "Refusé"

    listing = models.ForeignKey(
        "listings.Listing",
        related_name="candidate_introductions",
        on_delete=models.CASCADE,
    )
    profile = models.ForeignKey(
        "profiles.Profile",
        related_name="candidate_introductions",
        on_delete=models.CASCADE,
    )
    employer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="candidate_introductions_received",
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "profile"],
                name="uniq_candidate_intro_listing_profile",
            )
        ]
        indexes = [
            models.Index(fields=["employer", "status"]),
            models.Index(fields=["listing", "status"]),
        ]

    def __str__(self):
        return f"Intro {self.profile_id} → listing {self.listing_id} ({self.status})"

    @property
    def can_contact(self) -> bool:
        return self.status == self.Status.ACCEPTED
