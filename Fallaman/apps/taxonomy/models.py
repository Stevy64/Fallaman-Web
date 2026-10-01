"""Référentiel des métiers, et synonymes de recherche.

Les gens ne cherchent pas avec le vocabulaire du référentiel : ils tapent
« ménagère », « baby sitter », « cuistot ». Deux mécanismes répondent à cela :

* ``normalized_name`` — version sans accent ni ponctuation, recalculée à chaque
  ``save()``. C'est sur ce champ que porte la recherche, pour que « maçon » et
  « macon » ramènent la même chose.
* ``ProfessionAlias`` — synonymes rattachés à un métier. Une recherche qui tombe
  sur un alias remonte les annonces du métier correspondant.

``apps.listings.services.matching_profession_ids()`` exploite les deux. Ajouter
un synonyme suffit donc à améliorer la recherche, sans toucher au code.
"""

from django.db import models
from django.utils.text import slugify

from apps.core.utils import normalize_text


class Category(models.Model):
    name = models.CharField("nom", max_length=80)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=16, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "catégorie"
        verbose_name_plural = "catégories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Profession(models.Model):
    category = models.ForeignKey(Category, related_name="professions", on_delete=models.CASCADE)
    name = models.CharField("nom", max_length=120)
    slug = models.SlugField(max_length=140)
    normalized_name = models.CharField(max_length=140, db_index=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_popular = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        unique_together = ("category", "slug")
        verbose_name = "métier"
        verbose_name_plural = "métiers"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        self.normalized_name = normalize_text(self.name)
        super().save(*args, **kwargs)


class ProfessionAlias(models.Model):
    profession = models.ForeignKey(Profession, related_name="aliases", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    normalized_name = models.CharField(max_length=140, db_index=True, blank=True)

    class Meta:
        unique_together = ("profession", "name")
        verbose_name = "synonyme"
        verbose_name_plural = "synonymes"

    def __str__(self):
        return f"{self.name} → {self.profession}"

    def save(self, *args, **kwargs):
        self.normalized_name = normalize_text(self.name)
        super().save(*args, **kwargs)
