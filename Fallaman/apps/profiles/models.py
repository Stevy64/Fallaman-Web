"""Profil public d'un membre.

Créé automatiquement à l'inscription (``signals.create_profile``), avec le
numéro du compte repris comme WhatsApp par défaut.

``is_complete`` conditionne l'accès à la recommandation payante : un profil sans
nom, sans ville et sans métier ni présentation n'a rien à mettre en avant.

``recommended_until`` et ``recommend_score`` portent la recommandation payante,
alimentés par apps.recommendations. ``show_whatsapp`` pilote la visibilité du
numéro : ``apps.accounts.phone.contact_whatsapp_url()`` renvoie une chaîne vide
quand il est faux, ce qui masque le bouton partout.
"""

from django.conf import settings
from django.db import models

from apps.taxonomy.models import Profession


class Skill(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "compétence"

    def __str__(self):
        return self.name


class Profile(models.Model):
    class Availability(models.TextChoices):
        IMMEDIATE = "immediate", "Disponible immédiatement"
        WEEK = "week", "Cette semaine"
        FLEXIBLE = "flexible", "À définir"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="profile", on_delete=models.CASCADE)
    first_name = models.CharField("prénom", max_length=80, blank=True)
    last_name = models.CharField("nom", max_length=80, blank=True)
    display_name = models.CharField("nom affiché", max_length=80, blank=True)
    avatar = models.ImageField(upload_to="avatars/%Y/%m/", blank=True)
    bio = models.TextField("à propos", blank=True)
    city = models.ForeignKey("locations.City", null=True, blank=True, on_delete=models.SET_NULL)
    district = models.ForeignKey("locations.District", null=True, blank=True, on_delete=models.SET_NULL)
    primary_profession = models.ForeignKey(
        Profession, null=True, blank=True, related_name="primary_profiles", on_delete=models.SET_NULL
    )
    years_of_experience = models.PositiveSmallIntegerField("années d'expérience", null=True, blank=True)
    availability = models.CharField(max_length=20, choices=Availability.choices, blank=True)
    whatsapp_number = models.CharField("WhatsApp", max_length=20, blank=True)
    show_whatsapp = models.BooleanField("autoriser WhatsApp", default=True)
    is_public = models.BooleanField("profil public", default=True)
    cv_file = models.FileField(upload_to="cv/%Y/%m/", blank=True)
    looking_for = models.CharField("je recherche", max_length=160, blank=True)
    recommended_until = models.DateTimeField(null=True, blank=True, db_index=True)
    recommend_score = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "profil"

    def __str__(self):
        return self.display_name or self.user.phone_number

    @property
    def is_complete(self):
        return bool(self.display_name and self.city_id and (self.primary_profession_id or self.bio))

    @property
    def is_recommended(self):
        from django.utils import timezone

        return bool(self.recommended_until and self.recommended_until > timezone.now())


class ProfileSkill(models.Model):
    profile = models.ForeignKey(Profile, related_name="profile_skills", on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, related_name="profile_skills", on_delete=models.CASCADE)

    class Meta:
        unique_together = ("profile", "skill")
