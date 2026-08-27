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
