from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.core.utils import format_fcfa


class ListingQuerySet(models.QuerySet):
    def published(self):
        now = timezone.now()
        return self.filter(status=Listing.Status.PUBLISHED, expires_at__gt=now)

    def visible(self):
        return self.exclude(status__in=[Listing.Status.DELETED, Listing.Status.REJECTED])


class Listing(models.Model):
    class Type(models.TextChoices):
        EMPLOYMENT = "employment", "Emploi"
        MISSION = "mission", "Mission"

    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        PENDING = "pending_moderation", "En modération"
        PUBLISHED = "published", "Publiée"
        EXPIRED = "expired", "Expirée"
        FILLED = "filled", "Pourvue"
        HIDDEN = "hidden", "Masquée"
        REJECTED = "rejected", "Rejetée"
        DELETED = "deleted", "Supprimée"

    class SalaryType(models.TextChoices):
        MONTH = "month", "Par mois"
        WEEK = "week", "Par semaine"
        DAY = "day", "Par jour"
        TOTAL = "total", "Montant total"
        NEGOTIABLE = "negotiable", "À discuter"

    class Duration(models.TextChoices):
        TODAY = "today", "Aujourd'hui"
        FEW_DAYS = "few_days", "Quelques jours"
        FEW_WEEKS = "few_weeks", "Quelques semaines"
        FEW_MONTHS = "few_months", "Plusieurs mois"
        PERMANENT = "permanent", "Permanent"

    class Availability(models.TextChoices):
        IMMEDIATE = "immediate", "Dès maintenant"
        THIS_WEEK = "this_week", "Cette semaine"
        DATE = "date", "À une date précise"
        TBD = "tbd", "À définir"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="listings", on_delete=models.CASCADE
    )
    listing_type = models.CharField(max_length=20, choices=Type.choices)
    profession = models.ForeignKey(
        "taxonomy.Profession", null=True, blank=True, on_delete=models.SET_NULL
    )
    custom_profession = models.CharField(max_length=120, blank=True)
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, blank=True)
    description = models.TextField()
    province = models.ForeignKey("locations.Province", null=True, blank=True, on_delete=models.SET_NULL)
    city = models.ForeignKey("locations.City", null=True, blank=True, on_delete=models.SET_NULL)
    district = models.ForeignKey("locations.District", null=True, blank=True, on_delete=models.SET_NULL)
    salary_type = models.CharField(max_length=20, choices=SalaryType.choices, default=SalaryType.NEGOTIABLE)
    salary_amount = models.PositiveIntegerField(null=True, blank=True)
    duration = models.CharField(max_length=20, choices=Duration.choices, blank=True)
    availability = models.CharField(max_length=20, choices=Availability.choices, blank=True)
    work_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    boosted_until = models.DateTimeField(null=True, blank=True, db_index=True)
    boost_score = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ListingQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "expires_at"]),
            models.Index(fields=["listing_type", "status"]),
            models.Index(fields=["city", "status"]),
        ]
        verbose_name = "annonce"
        verbose_name_plural = "annonces"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.title:
            job = self.profession.name if self.profession else self.custom_profession or "quelqu'un"
            self.title = f"Recherche {job.lower()}"
        if not self.slug:
            self.slug = slugify(self.title)[:160]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("listings:detail", kwargs={"slug": self.slug, "pk": self.pk})

    @property
    def job_label(self):
        return (self.profession.name if self.profession else self.custom_profession) or "Mission"

    @property
    def location_label(self):
        parts = []
        if self.city:
            parts.append(self.city.name)
        if self.district:
            parts.append(self.district.name)
        return " · ".join(parts) or "Gabon"

    @property
    def salary_label(self):
        if self.salary_type == self.SalaryType.NEGOTIABLE or self.salary_amount is None:
            return "À discuter"
        unit = {
            self.SalaryType.MONTH: "/ mois",
            self.SalaryType.WEEK: "/ semaine",
            self.SalaryType.DAY: "/ jour",
            self.SalaryType.TOTAL: "",
        }.get(self.salary_type, "")
        return f"{format_fcfa(self.salary_amount)}{unit}"

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED and self.expires_at and self.expires_at > timezone.now()

    @property
    def is_boosted(self):
        return bool(self.boosted_until and self.boosted_until > timezone.now())

    def publish(self):
        was_live = self.status == self.Status.PUBLISHED
        now = timezone.now()
        days = (
            settings.LISTING_EMPLOYMENT_TTL_DAYS
            if self.listing_type == self.Type.EMPLOYMENT
            else settings.LISTING_MISSION_TTL_DAYS
        )
        self.status = self.Status.PUBLISHED
        self.published_at = now
        self.expires_at = now + timedelta(days=days)
        self.save(update_fields=["status", "published_at", "expires_at", "updated_at"])
        if not was_live:
            listing_id = self.pk

            def enqueue_match_notifications():
                from apps.listings.tasks import notify_listing_matches
                from apps.notifications.models import Notification
                from apps.notifications.services import notify_staff

                notify_listing_matches.delay(listing_id)
                notify_staff(
                    Notification.Kind.STAFF_NEW_LISTING,
                    f"Nouvelle annonce : {self.title}",
                    url=self.get_absolute_url(),
                )

            transaction.on_commit(enqueue_match_notifications)

    def renew(self):
        self.publish()

    def mark_filled(self):
        self.status = self.Status.FILLED
        self.save(update_fields=["status", "updated_at"])


class ListingImage(models.Model):
    listing = models.ForeignKey(Listing, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="listings/%Y/%m/")
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="favorites", on_delete=models.CASCADE)
    listing = models.ForeignKey(Listing, related_name="favorited_by", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "listing")
        verbose_name = "favori"


class SearchAlert(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="search_alerts", on_delete=models.CASCADE)
    query = models.CharField(max_length=120, blank=True)
    profession = models.ForeignKey("taxonomy.Profession", null=True, blank=True, on_delete=models.CASCADE)
    city = models.ForeignKey("locations.City", null=True, blank=True, on_delete=models.CASCADE)
    listing_type = models.CharField(max_length=20, choices=Listing.Type.choices, blank=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "alerte de recherche"
