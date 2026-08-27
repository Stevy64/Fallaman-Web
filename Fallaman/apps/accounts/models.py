from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .phone import normalize_phone


class UserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, email="", **extra_fields):
        if not phone_number:
            raise ValueError("Le numéro de téléphone est obligatoire.")
        extra_fields.setdefault("is_active", True)
        user = self.model(
            phone_number=normalize_phone(phone_number),
            email=self.normalize_email(email) if email else "",
            **extra_fields,
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("phone_verified", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Le superutilisateur doit avoir is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Le superutilisateur doit avoir is_superuser=True.")
        return self.create_user(phone_number, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    phone_number = models.CharField("téléphone", max_length=20, unique=True)
    phone_verified = models.BooleanField("téléphone vérifié", default=False)
    # Reçoit le code de première connexion et de réinitialisation. Non unique :
    # un foyer partage parfois une adresse. La conséquence est assumée — voir
    # apps/accounts/services.py, _resolve_activation_email().
    email = models.EmailField("adresse e-mail", blank=True)
    email_verified = models.BooleanField("e-mail vérifié", default=False)
    is_active = models.BooleanField("actif", default=True)
    is_staff = models.BooleanField("équipe", default=False)
    date_joined = models.DateTimeField("inscription", default=timezone.now)
    last_login = models.DateTimeField("dernière connexion", blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"
        ordering = ["-date_joined"]

    def __str__(self):
        profile = getattr(self, "profile", None)
        if profile and profile.display_name:
            return profile.display_name
        return self.phone_number

    @property
    def display_name(self):
        profile = getattr(self, "profile", None)
        if profile and profile.display_name:
            return profile.display_name
        return "Membre Fallaman"


class PhoneOTP(models.Model):
    phone_number = models.CharField(max_length=20, db_index=True)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "code OTP"
        verbose_name_plural = "codes OTP"

    def __str__(self):
        return f"OTP {self.phone_number}"
