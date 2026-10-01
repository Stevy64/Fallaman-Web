"""Sécurité du tunnel de paiement SingPay.

Ces tests verrouillent les invariants qui, s'ils sautent, permettent d'obtenir
une recommandation payante sans payer.
"""

import hashlib
import hmac
import json
import time
from unittest import mock

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.payments.models import PaymentTransaction, SingPayWebhookLog
from apps.payments.services.checkout import apply_payment_success, create_payment
from apps.payments.services.singpay import SingPayService
from apps.recommendations.models import RecommendationPurchase

WEBHOOK_SECRET = "secret-de-test-singpay"

SINGPAY_CONFIGURED = dict(
    SINGPAY_API_KEY="cle",
    SINGPAY_API_SECRET=WEBHOOK_SECRET,
    SINGPAY_MERCHANT_ID="wallet",
    DEV_CONVENIENCES=False,
)


def sign_gabomazone(payload: dict, timestamp: str, secret: str = WEBHOOK_SECRET) -> str:
    """Schéma exact utilisé en production sur Gabomazone.

    `_generate_signature()` y calcule HMAC-SHA256 sur `timestamp` concaténé au
    JSON trié et compact. Fallaman doit l'accepter tel quel.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(
        secret.encode(), f"{timestamp}{canonical}".encode(), hashlib.sha256
    ).hexdigest()


def sign(body: str, timestamp: str, secret: str = WEBHOOK_SECRET) -> str:
    return hmac.new(
        secret.encode(), f"{timestamp}{body}".encode(), hashlib.sha256
    ).hexdigest()


@pytest.fixture
def transaction(db, user):
    return PaymentTransaction.objects.create(
        user=user,
        purpose=PaymentTransaction.Purpose.PROFILE_BOOST,
        provider=PaymentTransaction.Provider.SINGPAY,
        amount=1200,
        description="Recommandation profil",
        reference="FLM-TEST-0001",
        provider_transaction_id="tx-remote-1",
        metadata={},
    )


def post_webhook(client, payload: dict, *, signature=None, timestamp=None, headers=True):
    body = json.dumps(payload)
    extra = {}
    if headers:
        ts = timestamp if timestamp is not None else str(int(time.time()))
        extra["HTTP_X_TIMESTAMP"] = ts
        extra["HTTP_X_SIGNATURE"] = signature if signature is not None else sign(body, ts)
    return client.post(
        reverse("payments:callback"),
        data=body,
        content_type="application/json",
        **extra,
    )


# ── Signature du webhook ────────────────────────────────────────────────


@pytest.mark.django_db
@override_settings(**SINGPAY_CONFIGURED)
def test_webhook_sans_signature_est_rejete(client, transaction):
    """Omettre l'en-tête de signature ne doit surtout pas valoir authentification."""
    response = post_webhook(
        client,
        {"order_id": transaction.reference, "status": "success"},
        headers=False,
    )
    assert response.status_code == 400
    transaction.refresh_from_db()
    assert transaction.status == PaymentTransaction.Status.PENDING


@pytest.mark.django_db
@override_settings(**SINGPAY_CONFIGURED)
def test_webhook_signature_invalide_est_rejete(client, transaction):
    response = post_webhook(
        client,
        {"order_id": transaction.reference, "status": "success"},
        signature="00" * 32,
    )
    assert response.status_code == 400
    transaction.refresh_from_db()
    assert transaction.status == PaymentTransaction.Status.PENDING


@pytest.mark.django_db
@override_settings(**SINGPAY_CONFIGURED)
def test_webhook_rejoue_hors_fenetre_est_rejete(client, transaction):
    """Un webhook légitime capturé hier ne doit pas pouvoir être rejoué."""
    vieux = str(int(time.time()) - 3600)
    response = post_webhook(
        client,
        {"order_id": transaction.reference, "status": "success"},
        timestamp=vieux,
    )
    assert response.status_code == 400
    transaction.refresh_from_db()
    assert transaction.status == PaymentTransaction.Status.PENDING


@pytest.mark.django_db
@override_settings(**SINGPAY_CONFIGURED)
def test_webhook_signe_mais_non_confirme_par_lapi_ne_credite_pas(client, transaction):
    """Le corps du webhook n'est jamais cru sur parole, même signé."""
    with mock.patch.object(
        SingPayService, "verify_payment", return_value=(False, {"error": "boom"})
    ):
        response = post_webhook(
            client, {"order_id": transaction.reference, "status": "success"}
        )
    assert response.status_code == 503
    transaction.refresh_from_db()
    assert transaction.status == PaymentTransaction.Status.PENDING


@pytest.mark.django_db
@override_settings(**SINGPAY_CONFIGURED)
def test_webhook_signe_et_confirme_credite(client, transaction):
    verified = {
        "status": "success",
        "amount": transaction.amount,
        "order_id": transaction.reference,
        "transaction_id": "tx-remote-1",
        "raw": {},
    }
    with mock.patch.object(SingPayService, "verify_payment", return_value=(True, verified)):
        response = post_webhook(
            client, {"order_id": transaction.reference, "status": "success"}
        )
    assert response.status_code == 200
    transaction.refresh_from_db()
    assert transaction.status == PaymentTransaction.Status.SUCCESS
    assert SingPayWebhookLog.objects.filter(signature_valid=True, processed=True).exists()


@pytest.mark.django_db
@override_settings(**SINGPAY_CONFIGURED)
def test_montant_encaisse_inferieur_ne_credite_pas(client, transaction):
    """Payer 100 F pour une prestation à 1200 F ne doit rien débloquer."""
    verified = {
        "status": "success",
        "amount": 100,
        "order_id": transaction.reference,
        "transaction_id": "tx-remote-1",
        "raw": {},
    }
    with mock.patch.object(SingPayService, "verify_payment", return_value=(True, verified)):
        post_webhook(client, {"order_id": transaction.reference, "status": "success"})
    transaction.refresh_from_db()
    assert transaction.status == PaymentTransaction.Status.PENDING


@pytest.mark.django_db
@override_settings(**SINGPAY_CONFIGURED)
def test_transaction_dun_tiers_ne_credite_pas(client, transaction):
    """Présenter l'identifiant d'un paiement réussi qui n'est pas le nôtre."""
    verified = {
        "status": "success",
        "amount": transaction.amount,
        "order_id": "FLM-AUTRE-9999",
        "transaction_id": "tx-remote-1",
        "raw": {},
    }
    with mock.patch.object(SingPayService, "verify_payment", return_value=(True, verified)):
        response = post_webhook(
            client, {"order_id": transaction.reference, "status": "success"}
        )
    assert response.status_code == 503
    transaction.refresh_from_db()
    assert transaction.status == PaymentTransaction.Status.PENDING


# ── Idempotence ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_double_encaissement_nactive_quune_fois(user, db):
    profile = user.profile
    profile.display_name = "Test"
    profile.save()
    tx = PaymentTransaction.objects.create(
        user=user,
        purpose=PaymentTransaction.Purpose.PROFILE_BOOST,
        provider=PaymentTransaction.Provider.SINGPAY,
        amount=1200,
        reference="FLM-IDEMP-1",
        metadata={},
    )
    purchase = RecommendationPurchase.objects.create(
        user=user,
        kind=RecommendationPurchase.Kind.PROFILE,
        profile=profile,
        payment=tx,
        duration_days=3,
        amount=1200,
        daily_rate=400,
    )

    assert apply_payment_success(tx, provider_transaction_id="x") is True
    purchase.refresh_from_db()
    premiere_fin = purchase.ends_at

    # Rejeu : webhook renvoyé par la passerelle, ou retour navigateur.
    assert apply_payment_success(tx, provider_transaction_id="x") is False
    purchase.refresh_from_db()
    assert purchase.ends_at == premiere_fin
    assert RecommendationPurchase.objects.filter(payment=tx).count() == 1


# ── Configuration obligatoire ───────────────────────────────────────────


@pytest.mark.django_db
@override_settings(SINGPAY_API_KEY="", SINGPAY_API_SECRET="", SINGPAY_MERCHANT_ID="")
def test_paiement_indisponible_sans_identifiants_singpay(user, rf):
    """Une configuration SingPay manquante rend le paiement indisponible, pas gratuit."""
    request = rf.get("/")
    request.user = user
    request.META["HTTP_HOST"] = "testserver"
    with pytest.raises(RuntimeError, match="n'est pas configuré"):
        create_payment(
            request=request,
            user=user,
            purpose=PaymentTransaction.Purpose.PROFILE_BOOST,
            amount=1200,
            description="test",
            metadata={},
        )


@pytest.mark.django_db
@override_settings(**SINGPAY_CONFIGURED)
def test_create_payment_redirige_vers_singpay(user, rf):
    request = rf.get("/")
    request.user = user
    request.META["HTTP_HOST"] = "testserver"
    init = {
        "payment_url": "https://gateway.singpay.ga/pay/abc",
        "transaction_id": "tx-init-1",
        "reference": "REF-FLM-1",
    }
    with mock.patch.object(SingPayService, "init_payment", return_value=(True, init)):
        tx, url = create_payment(
            request=request,
            user=user,
            purpose=PaymentTransaction.Purpose.PROFILE_BOOST,
            amount=1200,
            description="test",
            metadata={},
        )
    assert url == init["payment_url"]
    assert tx.provider == PaymentTransaction.Provider.SINGPAY
    assert tx.provider_transaction_id == "tx-init-1"


@pytest.mark.django_db
@override_settings(**SINGPAY_CONFIGURED)
def test_retour_navigateur_confirme_via_query_singpay(client, user, transaction):
    client.force_login(user)
    verified = {
        "status": "success",
        "amount": transaction.amount,
        "order_id": transaction.reference,
        "transaction_id": "tx-depuis-retour",
        "raw": {},
    }
    with mock.patch.object(SingPayService, "verify_payment", return_value=(True, verified)):
        response = client.get(
            reverse("payments:return", kwargs={"public_id": transaction.public_id}),
            {"transaction_id": "tx-depuis-retour"},
        )
    assert response.status_code == 302
    transaction.refresh_from_db()
    assert transaction.status == PaymentTransaction.Status.SUCCESS
    assert transaction.provider_transaction_id == "tx-depuis-retour"


# ── Client SingPay ──────────────────────────────────────────────────────


@override_settings(**SINGPAY_CONFIGURED)
def test_montant_envoye_en_entier():
    """Le FCFA n'a pas de centimes : aucun float ne doit partir chez SingPay."""
    service = SingPayService()
    with mock.patch.object(SingPayService, "_request", return_value=(True, {"link": "u"})) as req:
        service.init_payment(amount=1200, order_id="FLM-1", return_url="https://x/r")
    envoye = req.call_args[0][2]
    assert envoye["amount"] == 1200
    assert isinstance(envoye["amount"], int)
    assert set(envoye) <= {
        "portefeuille",
        "reference",
        "amount",
        "redirect_success",
        "redirect_error",
        "disbursement",
        "logoURL",
    }
    assert "phone" not in envoye
    assert "order_id" not in envoye
    assert "isTransfer" not in envoye


@override_settings(
    SINGPAY_API_KEY="cle",
    SINGPAY_API_SECRET="secret",
    SINGPAY_MERCHANT_ID="wallet",
    SINGPAY_DISBURSEMENT_ID="",
    SINGPAY_ENVIRONMENT="production",
)
def test_production_exige_le_disbursement():
    assert SingPayService().is_configured is False


@override_settings(**SINGPAY_CONFIGURED)
def test_montant_negatif_refuse():
    service = SingPayService()
    ok, detail = service.init_payment(amount=0, order_id="FLM-1", return_url="https://x/r")
    assert ok is False
    assert "amount" in detail["error"]


# ── Compatibilité Gabomazone ────────────────────────────────────────────


@pytest.mark.django_db
@override_settings(**SINGPAY_CONFIGURED)
def test_signature_au_schema_gabomazone_est_acceptee(client, transaction):
    """Le webhook signé comme le fait Gabomazone doit passer sans adaptation."""
    payload = {"order_id": transaction.reference, "status": "success", "z": 1, "a": 2}
    ts = str(int(time.time()))
    verified = {
        "status": "success",
        "amount": transaction.amount,
        "order_id": transaction.reference,
        "transaction_id": "tx-remote-1",
        "raw": {},
    }
    with mock.patch.object(SingPayService, "verify_payment", return_value=(True, verified)):
        response = client.post(
            reverse("payments:callback"),
            # Corps volontairement non trié : la signature porte sur le JSON trié.
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_TIMESTAMP=ts,
            HTTP_X_SIGNATURE=sign_gabomazone(payload, ts),
        )
    assert response.status_code == 200
    transaction.refresh_from_db()
    assert transaction.status == PaymentTransaction.Status.SUCCESS


@override_settings(**SINGPAY_CONFIGURED)
def test_horodatage_iso8601_reconnu():
    from datetime import UTC, datetime

    service = SingPayService()
    maintenant = datetime.now(UTC).isoformat()
    assert service._timestamp_freshness(maintenant) is True
    assert service._timestamp_freshness("2020-01-01T00:00:00+00:00") is False


@override_settings(**SINGPAY_CONFIGURED)
def test_horodatage_de_format_inconnu_ne_bloque_pas_le_webhook():
    """Le format de X-Timestamp n'est pas documenté par SingPay."""
    service = SingPayService()
    assert service._timestamp_freshness("20260826-153000-GMT") is None

    payload = {"order_id": "FLM-X", "status": "success"}
    body = json.dumps(payload)
    signature = sign_gabomazone(payload, "20260826-153000-GMT")
    assert service.verify_webhook_signature(body, signature, "20260826-153000-GMT") is True

    # Une fois le format identifié, le réglage permet de durcir.
    with override_settings(SINGPAY_WEBHOOK_REQUIRE_FRESH_TIMESTAMP=True):
        assert (
            SingPayService().verify_webhook_signature(
                body, signature, "20260826-153000-GMT"
            )
            is False
        )
