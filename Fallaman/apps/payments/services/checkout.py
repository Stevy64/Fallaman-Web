"""Création de paiements SingPay + mode simulé (développement uniquement)."""

from __future__ import annotations

import logging
import uuid

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.payments.models import PaymentTransaction
from apps.payments.services.singpay import singpay_service

logger = logging.getLogger(__name__)


def singpay_mock_enabled() -> bool:
    """
    Le paiement simulé crédite un achat sans encaisser un franc.

    Il ne s'active donc que sur demande explicite (``SINGPAY_MOCK``) ou en
    développement. Une configuration SingPay absente en production doit rendre
    le paiement *indisponible*, surtout pas gratuit.
    """
    if getattr(settings, "SINGPAY_MOCK", False):
        return True
    if singpay_service.is_configured:
        return False
    return bool(getattr(settings, "DEV_CONVENIENCES", False))


def build_absolute(request, path: str) -> str:
    return request.build_absolute_uri(path)


def create_payment(
    *,
    request,
    user,
    purpose: str,
    amount: int,
    description: str,
    metadata: dict,
) -> tuple[PaymentTransaction, str]:
    """
    Crée une transaction et renvoie (tx, payment_url).
    En simulation : URL vers la page de confirmation simulée.
    """
    amount = int(amount)
    if amount <= 0:
        raise RuntimeError("Montant de paiement invalide.")

    use_mock = singpay_mock_enabled()
    if not use_mock and not singpay_service.is_configured:
        raise RuntimeError(
            "Le service de paiement n'est pas configuré. Contactez l'équipe Fallaman."
        )

    reference = f"FLM-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8].upper()}"
    provider = (
        PaymentTransaction.Provider.MOCK if use_mock else PaymentTransaction.Provider.SINGPAY
    )

    tx = PaymentTransaction.objects.create(
        user=user,
        purpose=purpose,
        provider=provider,
        amount=amount,
        description=description,
        reference=reference,
        metadata=metadata,
    )

    return_url = build_absolute(
        request,
        reverse("payments:return", kwargs={"public_id": tx.public_id}),
    )
    callback_url = build_absolute(request, reverse("payments:callback"))

    if use_mock:
        payment_url = build_absolute(
            request,
            reverse("payments:mock_checkout", kwargs={"public_id": tx.public_id}),
        )
        tx.payment_url = payment_url
        tx.save(update_fields=["payment_url", "updated_at"])
        return tx, payment_url

    phone = getattr(user, "phone_number", "") or ""
    ok, data = singpay_service.init_payment(
        amount=amount,
        order_id=reference,
        return_url=return_url,
        callback_url=callback_url,
        customer_phone=phone,
        description=description,
    )
    if not ok or not data.get("payment_url"):
        tx.mark_failed()
        raise RuntimeError(data.get("error") or data.get("details") or "SingPay init failed")

    tx.provider_transaction_id = data.get("transaction_id") or ""
    tx.payment_url = data["payment_url"]
    tx.metadata = {**tx.metadata, "singpay_init": {"reference": data.get("reference")}}
    tx.save(update_fields=["provider_transaction_id", "payment_url", "metadata", "updated_at"])
    return tx, tx.payment_url


@transaction.atomic
def apply_payment_success(
    tx: PaymentTransaction,
    provider_transaction_id: str = "",
    verified_amount: int | None = None,
) -> bool:
    """
    Marque payé puis active la recommandation liée. Idempotent.

    Le verrou de ligne empêche qu'un webhook et un retour navigateur simultanés
    activent deux fois le même achat. ``verified_amount``, quand il est fourni,
    doit correspondre au montant attendu : un encaissement partiel ne donne pas
    droit à la prestation.
    """
    locked = PaymentTransaction.objects.select_for_update().get(pk=tx.pk)

    if verified_amount is not None and int(verified_amount) != int(locked.amount):
        logger.error(
            "[SingPay] montant discordant sur %s : attendu %s, encaissé %s",
            locked.reference,
            locked.amount,
            verified_amount,
        )
        return False

    if locked.status == PaymentTransaction.Status.SUCCESS:
        # Déjà traité : ne jamais réactiver l'achat une seconde fois.
        return False

    locked.mark_success(provider_transaction_id=provider_transaction_id)

    from apps.recommendations.services import activate_purchase_for_payment

    activate_purchase_for_payment(locked)

    # Garde l'instance de l'appelant cohérente avec la base.
    tx.status = locked.status
    tx.paid_at = locked.paid_at
    tx.provider_transaction_id = locked.provider_transaction_id
    return True
