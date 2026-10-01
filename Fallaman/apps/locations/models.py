"""Découpage géographique du Gabon : province → ville → quartier.

Les trois niveaux sont facultatifs sur une annonce : beaucoup de gens ne
précisent que la ville. La saisie est libre côté formulaire, puis rapprochée du
référentiel par ``apps.listings.location_utils.resolve_location()``, qui crée
l'entrée manquante plutôt que de rejeter la saisie.

``is_popular`` sert au raccourci de villes sur la page d'accueil.
"""

from django.db import models
from django.utils.text import slugify


class Province(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "province"
        verbose_name_plural = "provinces"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class City(models.Model):
    province = models.ForeignKey(Province, related_name="cities", on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    slug = models.SlugField()
    is_popular = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        unique_together = ("province", "slug")
        verbose_name = "ville"
        verbose_name_plural = "villes"
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class District(models.Model):
    city = models.ForeignKey(City, related_name="districts", on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    slug = models.SlugField()

    class Meta:
        ordering = ["name"]
        unique_together = ("city", "slug")
        verbose_name = "quartier"
        verbose_name_plural = "quartiers"

    def __str__(self):
        return f"{self.name} ({self.city})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
