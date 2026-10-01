"""Parcours de connexion : activation par e-mail, puis téléphone + mot de passe."""

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from apps.accounts.services import (
    ActivationBlockedError,
    OTPError,
    request_activation_code,
)

User = get_user_model()

MOT_DE_PASSE = "Libreville2026"

EMAIL_ACTIF = dict(
    OTP_PROVIDER="email",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST="smtp.test",
    DEV_CONVENIENCES=False,
)

CONSOLE_DEV = dict(OTP_PROVIDER="console", DEV_CONVENIENCES=True, OTP_DEV_CODE="123456")


def code_du_dernier_mail() -> str:
    corps = mail.outbox[-1].body
    for mot in corps.split():
        if mot.isdigit() and len(mot) == 6:
            return mot
    raise AssertionError(f"Aucun code à 6 chiffres dans : {corps!r}")


def activer(client, phone, email, password=MOT_DE_PASSE):
    """Déroule les trois étapes et renvoie la réponse finale."""
    client.post(reverse("accounts:activate"), {"phone_number": phone, "email": email})
    client.post(reverse("accounts:verify"), {"code": code_du_dernier_mail()})
    return client.post(
        reverse("accounts:set_password"),
        {"password1": password, "password2": password},
        follow=True,
    )


def test_home_is_public(client, db):
    response = client.get("/")
    assert response.status_code == 200
    assert "Trouvez quelqu'un" in response.content.decode()


def test_login_page(client):
    assert client.get(reverse("accounts:login")).status_code == 200


def test_activation_page(client):
    assert client.get(reverse("accounts:activate")).status_code == 200


# ── Première connexion ──────────────────────────────────────────────────


@pytest.mark.django_db
@override_settings(**EMAIL_ACTIF)
def test_premiere_connexion_cree_le_compte_et_le_mot_de_passe(client):
    response = activer(client, "06200030", "nouveau@exemple.com")

    assert response.status_code == 200
    assert "_auth_user_id" in client.session

    user = User.objects.get(phone_number="+24106200030")
    assert user.email == "nouveau@exemple.com"
    assert user.email_verified is True
    assert user.check_password(MOT_DE_PASSE)
    # Le code part par e-mail : rien ne prouve la possession du numéro.
    assert user.phone_verified is False


@pytest.mark.django_db
@override_settings(**EMAIL_ACTIF)
def test_le_code_part_bien_par_email(client):
    client.post(
        reverse("accounts:activate"),
        {"phone_number": "06200031", "email": "cible@exemple.com"},
    )
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["cible@exemple.com"]
    assert code_du_dernier_mail().isdigit()


@pytest.mark.django_db
@override_settings(**EMAIL_ACTIF)
def test_email_obligatoire_pour_un_nouveau_compte(client):
    response = client.post(reverse("accounts:activate"), {"phone_number": "06200032"})
    assert response.status_code == 200
    assert not mail.outbox
    assert not User.objects.filter(phone_number="+24106200032").exists()


@pytest.mark.django_db
@override_settings(**EMAIL_ACTIF)
def test_mot_de_passe_non_confirme_refuse(client):
    client.post(
        reverse("accounts:activate"),
        {"phone_number": "06200033", "email": "a@exemple.com"},
    )
    client.post(reverse("accounts:verify"), {"code": code_du_dernier_mail()})
    response = client.post(
        reverse("accounts:set_password"),
        {"password1": MOT_DE_PASSE, "password2": "autre-chose-2026"},
    )
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
@override_settings(**EMAIL_ACTIF)
def test_mot_de_passe_trop_faible_refuse(client):
    client.post(
        reverse("accounts:activate"),
        {"phone_number": "06200034", "email": "b@exemple.com"},
    )
    client.post(reverse("accounts:verify"), {"code": code_du_dernier_mail()})
    response = client.post(
        reverse("accounts:set_password"), {"password1": "12345678", "password2": "12345678"}
    )
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


# ── Vérification du code ────────────────────────────────────────────────


@pytest.mark.django_db
@override_settings(**EMAIL_ACTIF)
def test_code_errone_refuse(client):
    client.post(
        reverse("accounts:activate"),
        {"phone_number": "06200035", "email": "c@exemple.com"},
    )
    response = client.post(reverse("accounts:verify"), {"code": "000000"})
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_etape_mot_de_passe_inaccessible_sans_code_valide(client):
    """On ne doit pas pouvoir sauter la vérification en allant droit à l'URL."""
    response = client.get(reverse("accounts:set_password"))
    assert response.status_code == 302
    assert reverse("accounts:activate") in response["Location"]


@pytest.mark.django_db
def test_verification_inaccessible_sans_demande_prealable(client):
    response = client.get(reverse("accounts:verify"))
    assert response.status_code == 302
    assert reverse("accounts:activate") in response["Location"]


# ── Connexions suivantes ────────────────────────────────────────────────


@pytest.mark.django_db
@override_settings(**EMAIL_ACTIF)
def test_connexion_par_telephone_et_mot_de_passe(client):
    activer(client, "06200040", "membre@exemple.com")
    client.logout()

    response = client.post(
        reverse("accounts:login"),
        {"phone_number": "06200040", "password": MOT_DE_PASSE},
        follow=True,
    )
    assert response.status_code == 200
    assert "_auth_user_id" in client.session


@pytest.mark.django_db
@override_settings(**EMAIL_ACTIF)
def test_connexion_accepte_un_numero_mal_formate(client):
    activer(client, "06200041", "membre2@exemple.com")
    client.logout()

    # L'utilisateur ressaisit son numéro autrement qu'à l'inscription.
    response = client.post(
        reverse("accounts:login"),
        {"phone_number": "+241 06 20 00 41", "password": MOT_DE_PASSE},
        follow=True,
    )
    assert "_auth_user_id" in client.session
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(**EMAIL_ACTIF)
def test_mauvais_mot_de_passe_refuse(client):
    activer(client, "06200042", "membre3@exemple.com")
    client.logout()

    response = client.post(
        reverse("accounts:login"),
        {"phone_number": "06200042", "password": "mauvais-mot-de-passe"},
    )
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_numero_inconnu_ne_revele_rien(client):
    """Même message pour un numéro inconnu que pour un mot de passe faux."""
    response = client.post(
        reverse("accounts:login"),
        {"phone_number": "06209999", "password": "peu-importe"},
    )
    contenu = response.content.decode()
    assert "Numéro ou mot de passe incorrect" in contenu


# ── Réinitialisation du mot de passe ────────────────────────────────────


@pytest.mark.django_db
@override_settings(**EMAIL_ACTIF)
def test_mot_de_passe_oublie_renvoie_a_ladresse_enregistree(client):
    activer(client, "06200050", "vrai@exemple.com")
    client.logout()
    mail.outbox.clear()

    # L'attaquant connaît le numéro et tente de rediriger le code chez lui.
    client.post(
        reverse("accounts:activate"),
        {"phone_number": "06200050", "email": "attaquant@exemple.com"},
    )
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["vrai@exemple.com"]

    # …et l'adresse du compte reste inchangée après réinitialisation.
    client.post(reverse("accounts:verify"), {"code": code_du_dernier_mail()})
    client.post(
        reverse("accounts:set_password"),
        {"password1": "NouveauMotDePasse2026", "password2": "NouveauMotDePasse2026"},
    )
    user = User.objects.get(phone_number="+24106200050")
    assert user.email == "vrai@exemple.com"
    assert user.check_password("NouveauMotDePasse2026")


@pytest.mark.django_db
@override_settings(**EMAIL_ACTIF)
def test_compte_herite_sans_email_nest_pas_reclamable():
    """Un compte d'avant les mots de passe ne s'active pas en libre-service."""
    User.objects.create_user(phone_number="06200060", phone_verified=True)
    with pytest.raises(ActivationBlockedError):
        request_activation_code("06200060", "attaquant@exemple.com")
    assert not mail.outbox


@pytest.mark.django_db
@override_settings(**EMAIL_ACTIF)
def test_compte_suspendu_ne_recoit_pas_de_code():
    User.objects.create_user(
        phone_number="06200061", email="suspendu@exemple.com", is_active=False
    )
    with pytest.raises(OTPError):
        request_activation_code("06200061")
    assert not mail.outbox


# ── Canal console (développement) ───────────────────────────────────────


@pytest.mark.django_db
@override_settings(**CONSOLE_DEV)
def test_parcours_complet_en_mode_console(client):
    client.post(
        reverse("accounts:activate"),
        {"phone_number": "06200070", "email": "dev@exemple.com"},
    )
    client.post(reverse("accounts:verify"), {"code": "123456"})
    client.post(
        reverse("accounts:set_password"),
        {"password1": MOT_DE_PASSE, "password2": MOT_DE_PASSE},
    )
    assert "_auth_user_id" in client.session


# ── Où atterrit-on après connexion ? ────────────────────────────────────


@pytest.mark.django_db
@override_settings(**EMAIL_ACTIF)
def test_premiere_connexion_emmene_vers_le_profil(client):
    """Un profil vide ne sert à personne : on l'ouvre tout de suite."""
    client.post(
        reverse("accounts:activate"),
        {"phone_number": "06200080", "email": "arrivee@exemple.com"},
    )
    client.post(reverse("accounts:verify"), {"code": code_du_dernier_mail()})
    response = client.post(
        reverse("accounts:set_password"),
        {"password1": MOT_DE_PASSE, "password2": MOT_DE_PASSE},
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("profiles:mine")


@pytest.mark.django_db
@override_settings(**EMAIL_ACTIF)
def test_message_daccueil_a_la_premiere_connexion(client):
    response = activer(client, "06200081", "accueil@exemple.com")
    contenu = response.content.decode()
    assert "Bienvenue sur Fallaman" in contenu
    assert "Complétez votre profil" in contenu


@pytest.mark.django_db
@override_settings(**EMAIL_ACTIF)
def test_connexion_courante_atterrit_sur_laccueil(client):
    """Et non sur les favoris : le bouton de la navbar forçait next=/favoris/."""
    activer(client, "06200082", "retour@exemple.com")
    client.logout()

    response = client.post(
        reverse("accounts:login"),
        {"phone_number": "06200082", "password": MOT_DE_PASSE},
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("core:home")


@pytest.mark.django_db
@override_settings(**EMAIL_ACTIF)
def test_connexion_courante_respecte_un_next_legitime(client):
    """Cliquer sur une annonce en étant déconnecté doit y ramener après login."""
    activer(client, "06200083", "suite@exemple.com")
    client.logout()

    response = client.post(
        reverse("accounts:login"),
        {
            "phone_number": "06200083",
            "password": MOT_DE_PASSE,
            "next": reverse("listings:favorites"),
        },
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("listings:favorites")


@pytest.mark.django_db
@override_settings(**EMAIL_ACTIF)
def test_reinitialisation_ne_renvoie_pas_au_profil_si_deja_complet(client):
    """Un membre installé qui change son mot de passe n'a rien à recompléter."""
    activer(client, "06200084", "installe@exemple.com")
    user = User.objects.get(phone_number="+24106200084")
    profile = user.profile
    profile.display_name = "Membre Installé"
    profile.bio = "Déjà renseigné."
    from apps.locations.models import City, Province

    province = Province.objects.create(name="Estuaire")
    profile.city = City.objects.create(province=province, name="Libreville")
    profile.save()
    assert profile.is_complete
    client.logout()
    mail.outbox.clear()

    client.post(reverse("accounts:activate"), {"phone_number": "06200084"})
    client.post(reverse("accounts:verify"), {"code": code_du_dernier_mail()})
    response = client.post(
        reverse("accounts:set_password"),
        {"password1": "AutreMotDePasse2026", "password2": "AutreMotDePasse2026"},
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("core:home")
