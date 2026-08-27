from django import forms
from django.core.exceptions import ValidationError

from apps.core.uploads import max_listing_images, validate_image

from .models import Listing


class ListingTypeForm(forms.Form):
    listing_type = forms.ChoiceField(
        choices=Listing.Type.choices,
        label="Type d'annonce",
        widget=forms.RadioSelect,
    )


class ListingJobForm(forms.Form):
    job = forms.CharField(
        label="Métier recherché",
        min_length=2,
        max_length=120,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg",
                "list": "profession-suggestions",
                "placeholder": "Ex. Nounou, chauffeur, maçon…",
                "autocomplete": "off",
            }
        ),
    )

    def clean_job(self):
        return (self.cleaned_data.get("job") or "").strip()


class ListingLocationForm(forms.Form):
    province = forms.CharField(
        label="Province",
        max_length=80,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg",
                "list": "province-suggestions",
                "placeholder": "Ex. Estuaire",
                "autocomplete": "off",
            }
        ),
    )
    city = forms.CharField(
        label="Ville",
        max_length=80,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg",
                "list": "city-suggestions",
                "placeholder": "Ex. Libreville, Ntoum…",
                "autocomplete": "off",
            }
        ),
    )
    district = forms.CharField(
        label="Quartier (facultatif)",
        required=False,
        max_length=80,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg",
                "list": "district-suggestions",
                "placeholder": "Ex. Angondjé, Batterie IV…",
                "autocomplete": "off",
            }
        ),
    )

    def clean_province(self):
        return (self.cleaned_data.get("province") or "").strip()

    def clean_city(self):
        return (self.cleaned_data.get("city") or "").strip()

    def clean_district(self):
        return (self.cleaned_data.get("district") or "").strip()


class ListingTermsForm(forms.Form):
    duration = forms.ChoiceField(
        choices=Listing.Duration.choices,
        label="Pour combien de temps ?",
        widget=forms.RadioSelect,
    )
    salary_type = forms.ChoiceField(
        choices=Listing.SalaryType.choices,
        label="Rémunération",
        widget=forms.RadioSelect,
    )
    salary_amount = forms.IntegerField(
        required=False,
        min_value=0,
        label="Montant en FCFA",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control form-control-lg",
                "placeholder": "Ex. 150000",
                "inputmode": "numeric",
            }
        ),
    )
    availability = forms.ChoiceField(
        choices=Listing.Availability.choices,
        label="Quand avez-vous besoin de quelqu'un ?",
        widget=forms.RadioSelect,
    )
    work_date = forms.DateField(
        required=False,
        label="Date précise (facultatif)",
        widget=forms.DateInput(
            attrs={"class": "form-control form-control-lg", "type": "date"},
            format="%Y-%m-%d",
        ),
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
    )


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Accepte 0..n fichiers (évite l'erreur Django si aucune photo n'est choisie)."""

    def clean(self, data, initial=None):
        if not data:
            if self.required:
                return super().clean(data, initial)
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        limit = max_listing_images()
        if len(data) > limit:
            raise ValidationError(f"{limit} photos maximum par annonce.")
        result = []
        single_clean = super().clean
        for item in data:
            if item:
                result.append(validate_image(single_clean(item, initial), label="photo"))
        return result


class ListingDescriptionForm(forms.Form):
    description = forms.CharField(
        label="Décrivez ce que vous recherchez",
        min_length=20,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 6,
                "placeholder": "Ex. Je recherche une nounou sérieuse pour garder deux enfants…",
            }
        ),
    )
    images = MultipleFileField(
        required=False,
        label="Photos (facultatif)",
        widget=MultipleFileInput(
            attrs={"class": "form-control", "accept": "image/*"}
        ),
    )
