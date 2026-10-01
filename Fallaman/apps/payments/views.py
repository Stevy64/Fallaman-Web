import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.payments.models import PaymentTransaction, SingPayWebhookLog
from apps.payments.services.checkout import apply_payment_success
from apps.payments.services.singpay import (
    FAILURE_STATUSES,
    SUCCESS_STATUSES,
    singpay_service,
)

logger = logging.getLogger(__name__)

#: Un webhook ne doit jamais dépasser quelques kilo-octets.
MAX_WEBHOOK_BODY = 64 * 1024


def _extract_reference(payload: dict) -> str:
    reference = (
        payload.get("order_id") or payload.get("reference") or payload.get("ref") or ""
    )
    if not isinstance(reference, str):
        reference = str(reference or "")
    reference = reference.strip()
    # init_payment envoie la référence préfixée « REF- ».
    if reference.startswith("REF-"):
        reference = reference[4:]
    return reference


def _find_transaction(reference: str, provider_tx: str) -> PaymentTransaction | None:
    tx = None
    if reference:
        tx = PaymentTransaction.objects.filter(reference=reference).first()
    if not tx and provider_tx:
        tx = PaymentTransaction.objects.filter(provider_transaction_id=provider_tx).first()
    return tx


def _confirm_with_provider(tx: PaymentTransaction, provider_tx: str) -> tuple[str, int | None]:
    """
    Rejoue la vérification serveur-à-serveur.

    Retourne ``(statut, montant)`` tels que l'API SingPay les donne — jamais tels
    que le corps du webhook les prétend. ``("", None)`` si l'appel échoue : dans
    ce cas on ne décide rien.
    """
    candidate = provider_tx or tx.provider_transaction_id
    ok, data = (False, {})
    if candidate:
        ok, data = singpay_service.verify_payment(candidate)
    if not ok:
        ok, data = singpay_service.find_payment_by_reference(tx.reference)
    if not ok:
        logger.warning(
            "[SingPay] vérification impossible pour %s : %s", tx.reference, data.get("error")
        )
        return "", None

    # La transaction vérifiée doit bien porter sur *notre* commande, sinon un
    # tiers pourrait présenter l'identifiant d'un paiement réussi qui n'est pas
    # le sien pour faire créditer sa propre transaction.
    remote_order = str(data.get("order_id") or "").strip()
    if remote_order.startswith("REF-"):
        remote_order = remote_order[4:]
    if remote_order and remote_order != tx.reference:
        logger.error(
            "[SingPay] référence discordante : attendu %s, reçu %s", tx.reference, remote_order
        )
        return "", None

    amount = data.get("amount")
    try:
        amount = int(float(amount)) if amount is not None else None
    except (TypeError, ValueError):
        amount = None
    remote_id = str(data.get("transaction_id") or candidate or "").strip()
    if remote_id:
        _remember_provider_transaction_id(tx, remote_id)
    return str(data.get("status") or "").lower(), amount


@csrf_exempt
@require_POST
def singpay_callback(request):
    """
    Notification de paiement SingPay.

    Deux barrières indépendantes avant toute attribution de valeur :
    signature HMAC valide *et* statut reconfirmé auprès de l'API SingPay.
    """
    if len(request.body or b"") > MAX_WEBHOOK_BODY:
        return JsonResponse({"ok": False, "error": "payload too large"}, status=413)

    raw = request.body.decode("utf-8", errors="replace") if request.body else ""
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    signature = request.headers.get("X-Signature", "")
    timestamp = request.headers.get("X-Timestamp", "")

    # Signature obligatoire. Aucune valeur par défaut permissive : un webhook
    # sans en-tête de signature est un webhook non authentifié.
    valid = singpay_service.verify_webhook_signature(raw, signature, timestamp)

    log = SingPayWebhookLog.objects.create(
        payload=payload,
        headers={
            # On garde une empreinte, jamais la signature complète.
            "X-Signature": f"{signature[:8]}…" if signature else "",
            "X-Timestamp": timestamp,
        },
        signature_valid=valid,
    )
    if not valid:
        return JsonResponse({"ok": False, "error": "invalid signature"}, status=400)

    reference = _extract_reference(payload)
    provider_tx = _extract_provider_transaction_id(payload)
    tx = _find_transaction(reference, provider_tx)
    if tx:
        provider_tx = _remember_provider_transaction_id(tx, provider_tx)
    if not tx:
        # 200 volontaire : la passerelle n'a pas à rejouer indéfiniment un
        # événement qui ne nous concerne pas.
        logger.info("[SingPay] webhook sans transaction correspondante (ref=%s)", reference)
        return JsonResponse({"ok": True, "matched": False})

    status, amount = _confirm_with_provider(tx, provider_tx)
    if not status:
        # Vérification impossible : on laisse la passerelle réessayer.
        return JsonResponse({"ok": False, "error": "verification unavailable"}, status=503)

    processed = False
    if status in SUCCESS_STATUSES:
        processed = apply_payment_success(
            tx, provider_transaction_id=provider_tx, verified_amount=amount
        )
    elif status in FAILURE_STATUSES:
        processed = tx.mark_failed()

    if processed:
        log.processed = True
        log.save(update_fields=["processed"])
    return JsonResponse({"ok": True})


def _extract_provider_transaction_id(payload: dict) -> str:
    for key in ("transaction_id", "id", "transactionId", "provider_reference"):
        value = payload.get(key)
        if value:
            return str(value).strip()
    return ""


def _remember_provider_transaction_id(tx: PaymentTransaction, provider_tx: str) -> str:
    """Conserve l'identifiant SingPay dès qu'il apparaît (retour navigateur ou webhook)."""
    provider_tx = (provider_tx or "").strip()
    if provider_tx and provider_tx != tx.provider_transaction_id:
        tx.provider_transaction_id = provider_tx
        tx.save(update_fields=["provider_transaction_id", "updated_at"])
    return tx.provider_transaction_id or provider_tx


@login_required
@require_GET
def payment_return(request, public_id):
    """Retour navigateur : on reconfirme auprès de SingPay, jamais d'après l'URL."""
    tx = get_object_or_404(PaymentTransaction, public_id=public_id, user=request.user)

    query_tx = _extract_provider_transaction_id(request.GET)
    provider_tx = _remember_provider_transaction_id(tx, query_tx)

    if tx.status == PaymentTransaction.Status.PENDING:
        status, amount = _confirm_with_provider(tx, provider_tx)
        if status in SUCCESS_STATUSES:
            apply_payment_success(
                tx,
                provider_transaction_id=provider_tx,
                verified_amount=amount,
            )
            tx.refresh_from_db()
        elif status in FAILURE_STATUSES:
            tx.mark_failed()
            tx.refresh_from_db()

    if tx.status == PaymentTransaction.Status.SUCCESS:
        messages.success(request, "Paiement confirmé. Votre boost est actif.")
    elif tx.status == PaymentTransaction.Status.FAILED:
        messages.error(request, "Le paiement n'a pas abouti. Vous pouvez réessayer.")
    else:
        messages.info(request, "Paiement en cours de confirmation…")
    return redirect(_success_redirect(tx))


def _success_redirect(tx: PaymentTransaction):
    meta = tx.metadata or {}
    if tx.purpose == PaymentTransaction.Purpose.LISTING_BOOST and meta.get("listing_id"):
        from apps.listings.models import Listing

        listing = Listing.objects.filter(pk=meta["listing_id"]).first()
        if listing:
            return listing.get_absolute_url()
    if tx.purpose == PaymentTransaction.Purpose.PROFILE_BOOST:
        return "profiles:mine"
    return "recommendations:mine"
