"""Acheminement du code d'activation (console / e-mail / WhatsApp)."""

from unittest import mock

import pytest
import requests
from django.core import mail
from django.test import override_settings

from apps.accounts.models import PhoneOTP
from apps.accounts.otp_delivery import (
    OTPDeliveryError,
    deliver,
    deliver_email,
    deliver_whatsapp,
)
from apps.accounts.services import OTPError, request_activation_code

WHATSAPP_CONFIGURED = dict(
    OTP_PROVIDER="whatsapp",
    WHATSAPP_PHONE_NUMBER_ID="123456789",
    WHATSAPP_ACCESS_TOKEN="jeton-de-test",
    WHATSAPP_OTP_TEMPLATE="otp_code",
    WHATSAPP_OTP_LANGUAGE="fr",
    DEV_CONVENIENCES=False,
)


class FakeResponse:
    def __init__(self, status=200, text=""):
        self.status_code = status
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = self
            raise error


# ── Registre ────────────────────────────────────────────────────────────


@override_settings(OTP_PROVIDER="carrier-pigeon")
def test_canal_inconnu_est_signale_clairement():
    with pytest.raises(OTPDeliveryError) as exc:
        deliver("+24106200001", "123456", "x@exemple.com")
    assert "carrier-pigeon" in str(exc.value)


@override_settings(OTP_PROVIDER="console", DEV_CONVENIENCES=False)
def test_console_refuse_hors_developpement():
    with pytest.raises(OTPDeliveryError):
        deliver("+24106200001", "123456", "x@exemple.com")


# ── E-mail ──────────────────────────────────────────────────────────────

EMAIL_ACTIF = dict(
    OTP_PROVIDER="email",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="Fallaman <no-reply@fallaman.test>",
    OTP_CODE_TTL_SECONDS=300,
    DEV_CONVENIENCES=False,
)


@override_settings(**EMAIL_ACTIF)
def test_email_contient_le_code_et_la_duree():
    deliver_email("+24106200001", "482913", "membre@exemple.com")

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["membre@exemple.com"]
    assert message.from_email == "Fallaman <no-reply@fallaman.test>"
    assert "482913" in message.body
    assert "5 minutes" in message.body


@override_settings(**EMAIL_ACTIF)
def test_email_sans_destinataire_est_refuse():
    with pytest.raises(OTPDeliveryError):
        deliver_email("+24106200001", "482913", "")
    assert not mail.outbox


@override_settings(**EMAIL_ACTIF)
def test_panne_smtp_remonte_une_erreur_lisible():
    with mock.patch(
        "django.core.mail.send_mail", side_effect=OSError("connexion refusée")
    ):
        with pytest.raises(OTPDeliveryError) as exc:
            deliver_email("+24106200001", "482913", "membre@exemple.com")
    assert "e-mail" in str(exc.value)


# ── WhatsApp ────────────────────────────────────────────────────────────


@override_settings(**WHATSAPP_CONFIGURED)
def test_whatsapp_envoie_un_modele_dauthentification():
    with mock.patch("apps.accounts.otp_delivery.requests.post") as post:
        post.return_value = FakeResponse()
        deliver_whatsapp("+24106200001", "482913", "")

    url = post.call_args[0][0]
    assert url == "https://graph.facebook.com/v21.0/123456789/messages"
    assert post.call_args[1]["headers"]["Authorization"] == "Bearer jeton-de-test"

    corps = post.call_args[1]["json"]
    # L'API Meta attend le numéro international sans le « + ».
    assert corps["to"] == "24106200001"
    assert corps["template"]["name"] == "otp_code"
    assert corps["template"]["language"]["code"] == "fr"

    composants = corps["template"]["components"]
    assert composants[0]["parameters"][0]["text"] == "482913"
    # Le bouton « copier le code » doit répéter le code.
    bouton = next(c for c in composants if c["type"] == "button")
    assert bouton["parameters"][0]["text"] == "482913"


@override_settings(**WHATSAPP_CONFIGURED, WHATSAPP_OTP_HAS_COPY_BUTTON=False)
def test_bouton_copier_desactivable():
    with mock.patch("apps.accounts.otp_delivery.requests.post") as post:
        post.return_value = FakeResponse()
        deliver_whatsapp("+24106200001", "482913", "")
    composants = post.call_args[1]["json"]["template"]["components"]
    assert all(c["type"] != "button" for c in composants)


@override_settings(OTP_PROVIDER="whatsapp", WHATSAPP_PHONE_NUMBER_ID="", WHATSAPP_ACCESS_TOKEN="")
def test_whatsapp_non_configure_est_signale():
    with pytest.raises(OTPDeliveryError) as exc:
        deliver_whatsapp("+24106200001", "123456", "")
    assert "WHATSAPP_PHONE_NUMBER_ID" in str(exc.value)


@override_settings(**WHATSAPP_CONFIGURED)
def test_erreur_api_ne_fuit_pas_le_jeton():
    """Le message rendu à l'utilisateur ne doit pas exposer le jeton d'accès."""
    with mock.patch("apps.accounts.otp_delivery.requests.post") as post:
        post.return_value = FakeResponse(401, '{"error":"Bad token jeton-de-test"}')
        with pytest.raises(OTPDeliveryError) as exc:
            deliver_whatsapp("+24106200001", "123456", "")
    assert "jeton-de-test" not in str(exc.value)


# ── Intégration avec request_otp ────────────────────────────────────────


@pytest.mark.django_db
@override_settings(**WHATSAPP_CONFIGURED)
def test_request_otp_passe_par_whatsapp():
    with mock.patch("apps.accounts.otp_delivery.requests.post") as post:
        post.return_value = FakeResponse()
        retourne = request_activation_code("+24106200002", "a@exemple.com")

    assert retourne == ""  # jamais renvoyé au client hors développement
    assert PhoneOTP.objects.filter(phone_number="+24106200002").count() == 1
    envoye = post.call_args[1]["json"]["template"]["components"][0]
    code = envoye["parameters"][0]["text"]
    assert code.isdigit() and len(code) == 6
    assert code != "123456"  # code aléatoire, pas le code de développement


@pytest.mark.django_db
@override_settings(**WHATSAPP_CONFIGURED)
def test_echec_denvoi_ne_consomme_pas_le_quota():
    """Un code jamais reçu ne doit pas amputer les 5 demandes / 10 min."""
    with mock.patch("apps.accounts.otp_delivery.requests.post") as post:
        post.return_value = FakeResponse(500, "boom")
        with pytest.raises(OTPError):
            request_activation_code("+24106200003", "b@exemple.com")

    assert PhoneOTP.objects.filter(phone_number="+24106200003").count() == 0
