from django import forms

from apps.core.uploads import validate_document, validate_image
from apps.listings.location_utils import resolve_location, resolve_profession
from apps.locations.models import City

from .models import Profile


class ProfileForm(forms.ModelForm):
    city_name = forms.CharField(
        label="Ville",
        required=False,
        max_length=80,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "list": "city-suggestions",
                "placeholder": "Ex. Libreville",
                "autocomplete": "off",
            }
        ),
    )
    district_name = forms.CharField(
        label="Quartier",
        required=False,
        max_length=80,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "list": "district-suggestions",
                "placeholder": "Ex. Angondjé",
                "autocomplete": "off",
            }
        ),
    )
    profession_name = forms.CharField(
        label="Métier principal",
        required=False,
        max_length=120,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "list": "profession-suggestions",
                "placeholder": "Ex. Nounou, chauffeur…",
                "autocomplete": "off",
            }
        ),
    )
    province_name = forms.CharField(
        label="Province",
        required=False,
        max_length=80,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "list": "province-suggestions",
                "placeholder": "Ex. Estuaire",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = Profile
        fields = [
            "first_name",
            "last_name",
            "display_name",
            "bio",
            "years_of_experience",
            "availability",
            "whatsapp_number",
            "show_whatsapp",
            "looking_for",
            "cv_file",
            "avatar",
        ]
        labels = {
            "first_name": "Prénom",
            "last_name": "Nom",
            "display_name": "Nom affiché",
            "bio": "À propos",
            "years_of_experience": "Années d'expérience",
            "availability": "Disponibilité",
            "whatsapp_number": "Numéro WhatsApp",
            "show_whatsapp": "Autoriser le contact WhatsApp",
            "looking_for": "Je recherche",
            "cv_file": "CV (facultatif)",
            "avatar": "Photo de profil",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Votre prénom"}),
            "last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Votre nom"}),
            "display_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nom visible sur Fallaman"}),
            "bio": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Parlez un peu de vous…",
                }
            ),
            "years_of_experience": forms.NumberInput(
                attrs={"class": "form-control", "min": 0, "placeholder": "Ex. 3"}
            ),
            "availability": forms.RadioSelect,
            "whatsapp_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "077 00 00 00"}
            ),
            "show_whatsapp": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "looking_for": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex. Emploi nounou ou missions ménage",
                }
            ),
            "cv_file": forms.FileInput(attrs={"class": "form-control", "accept": ".pdf,.doc,.docx,image/*"}),
            "avatar": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance") or getattr(self, "instance", None)
        if instance and instance.pk:
            if instance.city:
                self.fields["city_name"].initial = instance.city.name
                if instance.city.province_id:
                    self.fields["province_name"].initial = instance.city.province.name
            if instance.district:
                self.fields["district_name"].initial = instance.district.name
            if instance.primary_profession:
                self.fields["profession_name"].initial = instance.primary_profession.name
        for field in self.fields.values():
            field.required = False
        # Field order
        desired = [
            "first_name",
            "last_name",
            "display_name",
            "bio",
            "province_name",
            "city_name",
            "district_name",
            "profession_name",
            "years_of_experience",
            "availability",
            "looking_for",
            "whatsapp_number",
            "show_whatsapp",
            "avatar",
            "cv_file",
        ]
        self.order_fields(desired)

    def clean_avatar(self):
        return validate_image(self.cleaned_data.get("avatar"), label="photo de profil")

    def clean_cv_file(self):
        return validate_document(self.cleaned_data.get("cv_file"), label="CV")

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.display_name:
            parts = [instance.first_name, instance.last_name]
            instance.display_name = " ".join(p for p in parts if p).strip()

        city_name = (self.cleaned_data.get("city_name") or "").strip()
        district_name = (self.cleaned_data.get("district_name") or "").strip()
        province_name = (self.cleaned_data.get("province_name") or "").strip()
        if city_name:
            if not province_name:
                existing = City.objects.filter(name__iexact=city_name).select_related("province").first()
                province_name = existing.province.name if existing else "Estuaire"
            province, city, district = resolve_location(province_name, city_name, district_name)
            instance.city = city
            instance.district = district
        else:
            instance.city = None
            instance.district = None

        profession, custom = resolve_profession(self.cleaned_data.get("profession_name") or "")
        if profession:
            instance.primary_profession = profession
        elif custom:
            # Keep free-text métier in looking_for if no taxonomy match and looking_for empty
            instance.primary_profession = None
            if not instance.looking_for:
                instance.looking_for = custom
        else:
            instance.primary_profession = None

        if commit:
            instance.save()
        return instance
