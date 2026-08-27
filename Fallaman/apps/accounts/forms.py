from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError

from .phone import normalize_phone


class LoginForm(forms.Form):
    """Connexion courante : numéro + mot de passe."""

    phone_number = forms.CharField(
        label="Votre numéro de téléphone",
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg",
                "placeholder": "077 00 00 00",
                "inputmode": "tel",
                "autocomplete": "tel",
            }
        ),
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control form-control-lg",
                "autocomplete": "current-password",
                "placeholder": "Votre mot de passe",
            }
        ),
    )
    next = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_phone_number(self):
        # Pas de normalize_phone ici : un numéro mal formé ne doit pas produire
        # un message différent d'un mot de passe faux (énumération de comptes).
        return (self.cleaned_data.get("phone_number") or "").strip()


class ActivationForm(forms.Form):
    """Première connexion ou mot de passe oublié."""

    phone_number = forms.CharField(
        label="Votre numéro de téléphone",
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg",
                "placeholder": "077 00 00 00",
                "inputmode": "tel",
                "autocomplete": "tel",
            }
        ),
    )
    email = forms.EmailField(
        label="Votre adresse e-mail",
        required=False,
        help_text="Nécessaire pour une première connexion. Le code y sera envoyé.",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control form-control-lg",
                "placeholder": "vous@exemple.com",
                "inputmode": "email",
                "autocomplete": "email",
            }
        ),
    )
    next = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_phone_number(self):
        return normalize_phone(self.cleaned_data["phone_number"])

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip()


class OTPForm(forms.Form):
    code = forms.CharField(
        label="Code reçu par SMS",
        max_length=6,
        min_length=4,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg text-center",
                "placeholder": "123456",
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
            }
        ),
    )
    next = forms.CharField(required=False, widget=forms.HiddenInput)


class ChoosePasswordForm(forms.Form):
    """Pose du mot de passe, juste après validation du code."""

    password1 = forms.CharField(
        label="Choisissez un mot de passe",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control form-control-lg",
                "autocomplete": "new-password",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirmez le mot de passe",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control form-control-lg",
                "autocomplete": "new-password",
            }
        ),
    )
    next = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean(self):
        data = super().clean()
        if data.get("password1") and data.get("password1") != data.get("password2"):
            self.add_error("password2", "Les deux mots de passe ne correspondent pas.")
        return data


class StaffPasswordForm(forms.Form):
    phone_number = forms.CharField(
        label="Téléphone",
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg",
                "placeholder": "+241 06 11 11 11",
                "inputmode": "tel",
                "autocomplete": "username",
            }
        ),
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control form-control-lg",
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
    )
    next = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_phone_number(self):
        return normalize_phone(self.cleaned_data["phone_number"])

    def clean_password(self):
        return (self.cleaned_data.get("password") or "").strip()


class FallamanAdminAuthenticationForm(AdminAuthenticationForm):
    """Normalise le téléphone avant l'auth Django Admin."""

    def clean_username(self):
        raw = (self.cleaned_data.get("username") or "").strip()
        try:
            return normalize_phone(raw)
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc
