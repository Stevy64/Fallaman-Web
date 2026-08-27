"""Durcissements transverses : redirections, téléversements, OTP, compte démo."""

import io

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.urls import reverse

from apps.accounts.services import OTPError, request_activation_code
from apps.core.redirects import is_safe_target
from apps.core.uploads import validate_document, validate_image

# ── Redirections ouvertes ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "target",
    [
        "//evil.tld",
        "https://evil.tld/phishing",
        "//evil.tld/connexion",
        "http://evil.tld",
        "\\\\evil.tld",
    ],
)
def test_cibles_externes_refusees(target):
    """`startswith('/')` laissait passer `//evil.tld`, qui change de domaine."""
    assert is_safe_target(target) is False


@pytest.mark.parametrize("target", ["/annonces/", "/profil/moi/", "/messages/12/"])
def test_cibles_internes_acceptees(target):
    assert is_safe_target(target) is True


@pytest.mark.django_db
@override_settings(DEV_CONVENIENCES=True, OTP_PROVIDER="console", OTP_DEV_CODE="123456")
def test_activation_ne_redirige_pas_hors_du_site(client, db):
    """Le paramètre `next` ne doit pas servir de tremplin vers un site tiers."""
    client.post(
        reverse("accounts:activate"),
        {"phone_number": "06200077", "email": "x@exemple.com", "next": "//evil.tld"},
    )
    client.post(reverse("accounts:verify"), {"code": "123456"})
    response = client.post(
        reverse("accounts:set_password"),
        {"password1": "Libreville2026", "password2": "Libreville2026"},
    )
    assert response.status_code == 302
    assert "evil.tld" not in response["Location"]


@pytest.mark.django_db
@override_settings(DEV_CONVENIENCES=True, OTP_PROVIDER="console", OTP_DEV_CODE="123456")
def test_connexion_ne_redirige_pas_hors_du_site(client, db):
    get_user_model().objects.create_user(
        phone_number="+24106200078", password="Libreville2026", email="y@exemple.com"
    )
    response = client.post(
        reverse("accounts:login"),
        {
            "phone_number": "06200078",
            "password": "Libreville2026",
            "next": "//evil.tld",
        },
    )
    assert response.status_code == 302
    assert "evil.tld" not in response["Location"]


# ── Téléversements ──────────────────────────────────────────────────────


def _upload(name, content=b"x", content_type="image/png"):
    return SimpleUploadedFile(name, content, content_type=content_type)


def test_html_deguise_en_cv_est_refuse():
    """Un .html servi depuis notre domaine s'exécuterait avec nos cookies."""
    with pytest.raises(ValidationError):
        validate_document(_upload("cv.html", b"<script>", "text/html"), label="CV")


def test_svg_refuse_comme_image():
    """Le SVG embarque du script : hors de la liste blanche."""
    with pytest.raises(ValidationError):
        validate_image(_upload("avatar.svg", b"<svg/>", "image/svg+xml"))


def test_extension_valide_mais_type_mime_incoherent_refuse():
    with pytest.raises(ValidationError):
        validate_image(_upload("avatar.png", b"MZ", "application/x-msdownload"))


@override_settings(MAX_UPLOAD_SIZE=1024)
def test_fichier_trop_lourd_refuse():
    with pytest.raises(ValidationError):
        validate_image(_upload("photo.jpg", b"a" * 2048, "image/jpeg"))


def test_image_valide_acceptee():
    fichier = _upload("photo.jpg", b"a" * 10, "image/jpeg")
    assert validate_image(fichier) is fichier


@override_settings(MAX_LISTING_IMAGES=2)
@pytest.mark.django_db
def test_nombre_de_photos_plafonne():
    from apps.listings.forms import ListingDescriptionForm

    form = ListingDescriptionForm(
        {"description": "Une description suffisamment longue pour valider."},
        {"images": [_upload(f"p{i}.jpg", b"a", "image/jpeg") for i in range(3)]},
    )
    assert not form.is_valid()
    assert "images" in form.errors


# ── OTP ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
@override_settings(OTP_PROVIDER="console", DEV_CONVENIENCES=False)
def test_otp_console_refuse_hors_developpement():
    """Sinon le code est figé à OTP_DEV_CODE pour tous les comptes."""
    with pytest.raises(OTPError):
        request_activation_code("+24106200088", "a@exemple.com")


@pytest.mark.django_db
@override_settings(OTP_PROVIDER="console", DEV_CONVENIENCES=True, OTP_DEV_CODE="123456")
def test_otp_console_fonctionne_en_developpement():
    assert request_activation_code("+24106200089", "b@exemple.com") == "123456"


# ── Compte de démonstration ─────────────────────────────────────────────


@pytest.mark.django_db
@override_settings(DEV_CONVENIENCES=False)
def test_seed_demo_refuse_de_creer_ladmin_hors_developpement():
    """Ce compte a un mot de passe publié dans le dépôt."""
    with pytest.raises(CommandError):
        call_command("seed_demo", "--with-accounts", stdout=io.StringIO())


@pytest.mark.django_db
@override_settings(DEV_CONVENIENCES=False)
def test_seed_demo_reference_only_ne_cree_aucun_compte():
    call_command("seed_demo", "--reference-only", stdout=io.StringIO())
    assert get_user_model().objects.count() == 0
