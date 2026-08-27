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
