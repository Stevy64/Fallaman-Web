"""Profil : préremplissage du WhatsApp et champs d'identité obligatoires."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.profiles.forms import ProfileForm

User = get_user_model()


@pytest.mark.django_db
def test_whatsapp_prerempli_avec_le_numero_du_compte():
    """Le numéro saisi à l'inscription ne doit pas être redemandé."""
    user = User.objects.create_user(phone_number="06200090")
    assert user.profile.whatsapp_number == "+24106200090"


@pytest.mark.django_db
def test_formulaire_affiche_le_numero_du_compte(user):
    """Même sur un profil dont le champ serait resté vide."""
    profile = user.profile
    profile.whatsapp_number = ""
    profile.save(update_fields=["whatsapp_number"])

    form = ProfileForm(instance=profile)
    assert form.fields["whatsapp_number"].initial == user.phone_number


@pytest.mark.django_db
def test_identite_obligatoire(user):
    form = ProfileForm(instance=user.profile)
    for champ in ("first_name", "last_name", "whatsapp_number"):
        assert form.fields[champ].required is True, champ
    # Le reste demeure facultatif.
    assert form.fields["bio"].required is False
    assert form.fields["city_name"].required is False


@pytest.mark.django_db
def test_profil_refuse_sans_nom_ni_numero(user):
    form = ProfileForm({"first_name": "", "last_name": "", "whatsapp_number": ""},
                       instance=user.profile)
    assert not form.is_valid()
    assert set(form.errors) >= {"first_name", "last_name", "whatsapp_number"}


@pytest.mark.django_db
def test_numero_invalide_refuse(user):
    form = ProfileForm(
        {"first_name": "Awa", "last_name": "Nzé", "whatsapp_number": "12"},
        instance=user.profile,
    )
    assert not form.is_valid()
    assert "whatsapp_number" in form.errors


@pytest.mark.django_db
def test_numero_normalise_en_e164(user):
    form = ProfileForm(
        {"first_name": "Awa", "last_name": "Nzé", "whatsapp_number": "077 88 99 00"},
        instance=user.profile,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["whatsapp_number"] == "+24177889900"


@pytest.mark.django_db
def test_enregistrement_via_la_vue(client, user):
    client.force_login(user)
    response = client.post(
        reverse("profiles:mine"),
        {"first_name": "Awa", "last_name": "Nzé", "whatsapp_number": "077 88 99 00"},
    )
    assert response.status_code == 302
    user.profile.refresh_from_db()
    assert user.profile.whatsapp_number == "+24177889900"
    assert user.profile.display_name == "Awa Nzé"
