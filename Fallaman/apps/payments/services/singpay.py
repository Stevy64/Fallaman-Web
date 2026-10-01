"""Client SingPay — init, verify, webhook HMAC.

Principe de sécurité : le webhook n'est qu'un *déclencheur*. La source de
vérité reste l'API SingPay, interrogée serveur-à-serveur avant toute
attribution de valeur (cf. apps.payments.views.singpay_callback).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests
from django.conf import settings

logger = logging.getLogger(__name__)
LOG_PREFIX = "[SingPay]"

#: Statuts fournisseur considérés comme un encaissement effectif.
SUCCESS_STATUSES = frozenset(
    {"success", "successful", "paid", "completed", "done", "ok", "validated"}
)
#: Statuts fournisseur considérés comme définitivement échoués.
FAILURE_STATUSES = frozenset(
    {"failed", "error", "cancelled", "canceled", "expired", "rejected", "fail"}
)


class SingPayError(Exception):
    pass


class SingPayService:
    BASE_URL = "https://gateway.singpay.ga"
    #: Délai max entre l'horodatage signé et la réception (anti-rejeu).
    DEFAULT_TOLERANCE_SECONDS = 300

    # Les identifiants sont lus à chaque accès, jamais figés à l'import : une
    # instance mise en cache au chargement du module garderait sinon la
    # configuration du premier import, y compris après rotation des clés.
    @property
    def api_key(self) -> str:
        return getattr(settings, "SINGPAY_API_KEY", "") or ""

    @property
    def api_secret(self) -> str:
        return getattr(settings, "SINGPAY_API_SECRET", "") or ""

    @property
    def merchant_id(self) -> str:
        return getattr(settings, "SINGPAY_MERCHANT_ID", "") or ""

    @property
    def disbursement_id(self) -> str:
        return getattr(settings, "SINGPAY_DISBURSEMENT_ID", "") or ""

    @property
    def environment(self) -> str:
        return getattr(settings, "SINGPAY_ENVIRONMENT", "sandbox")

    @property
    def base_url(self) -> str:
        return getattr(settings, "SINGPAY_BASE_URL", "") or self.BASE_URL

    @property
    def webhook_secret(self) -> str:
        """Secret de signature du webhook (retombe sur l'API secret par défaut)."""
        return getattr(settings, "SINGPAY_WEBHOOK_SECRET", "") or self.api_secret

    @property
    def tolerance_seconds(self) -> int:
        return int(
            getattr(settings, "SINGPAY_WEBHOOK_TOLERANCE_SECONDS", self.DEFAULT_TOLERANCE_SECONDS)
        )

    @property
    def logo_url(self) -> str:
        return getattr(settings, "SINGPAY_LOGO_URL", "") or ""

    @property
    def is_configured(self) -> bool:
        required = bool(self.api_key and self.api_secret and self.merchant_id)
        if (self.environment or "").lower() == "production":
            return required and bool(self.disbursement_id)
        return required

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "accept": "*/*",
            "x-client-id": self.api_key,
            "x-client-secret": self.api_secret,
            "x-wallet": self.merchant_id,
        }

    def _request(self, method: str, endpoint: str, data: dict | None = None) -> tuple[bool, dict]:
        if not self.is_configured:
            return False, {
                "error": "SingPay credentials missing",
                "details": "Configure SINGPAY_API_KEY, SINGPAY_API_SECRET, SINGPAY_MERCHANT_ID",
            }
        url = f"{self.base_url}{endpoint}"
        headers = self._headers()
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=data or {}, timeout=30)
            else:
                response = requests.post(url, headers=headers, json=data or {}, timeout=30)
            response.raise_for_status()
            payload = response.json() if response.content else {}
            if not isinstance(payload, dict):
                return True, {"data": payload}
            # Certaines erreurs SingPay arrivent en HTTP 200 avec un champ error.
            if payload.get("error") and not (
                payload.get("link") or payload.get("payment_url") or payload.get("status")
            ):
                return False, {"error": str(payload.get("error")), "response": payload}
            return True, payload
        except requests.RequestException as exc:
            # Pas de logger.exception ici : la trace embarque la requête, donc les
            # en-têtes x-client-secret.
            logger.warning("%s request failed endpoint=%s error=%s", LOG_PREFIX, endpoint, exc)
            detail: dict[str, Any] = {"error": str(exc)}
            if getattr(exc, "response", None) is not None:
                try:
                    detail["response"] = exc.response.json()
                except ValueError:
                    detail["response_text"] = (exc.response.text or "")[:300]
            return False, detail

    def _extract_transaction_id(self, payment_url: str, response: dict) -> str:
        for key in ("transaction_id", "id", "transactionId"):
            value = response.get(key)
            if value:
                return str(value)
        if not payment_url:
            return ""
        if "/payment/" in payment_url:
            return payment_url.split("/payment/")[-1].split("/")[0].split("?")[0]
        if "transaction_id=" in payment_url:
            params = parse_qs(urlparse(payment_url).query)
            if params.get("transaction_id"):
                return params["transaction_id"][0]
        match = re.search(
            r"/([a-f0-9]{8,}-[a-f0-9]{4,}-[a-f0-9]{4,}-[a-f0-9]{4,}-[a-f0-9]{12,})",
            payment_url,
            re.IGNORECASE,
        )
        return match.group(1) if match else ""

    def init_payment(
        self,
        *,
        amount: int,
        order_id: str,
        return_url: str,
        callback_url: str = "",
        customer_phone: str = "",
        description: str = "",
    ) -> tuple[bool, dict]:
        # Le FCFA n'a pas de subdivision : on reste en entier, jamais en float.
        amount = int(amount)
        if amount <= 0:
            return False, {"error": "invalid amount", "details": "Le montant doit être positif."}
        # Corps aligné sur le SDK officiel (generatePaymentLink) : les champs
        # supplémentaires (phone, order_id, callback_url…) font échouer /ext.
        data = {
            "portefeuille": self.merchant_id,
            "reference": f"REF-{order_id}",
            "amount": amount,
            "redirect_success": return_url,
            "redirect_error": return_url,
        }
        if self.disbursement_id:
            data["disbursement"] = self.disbursement_id
        if self.logo_url:
            data["logoURL"] = self.logo_url

        success, response = self._request("POST", "/v1/ext", data)
        if not success:
            return False, response

        payment_url = response.get("link") or response.get("payment_url") or ""
        transaction_id = self._extract_transaction_id(payment_url, response)
        return True, {
            "payment_url": payment_url,
            "transaction_id": transaction_id,
            "reference": response.get("reference") or f"REF-{order_id}",
            "expires_at": response.get("exp"),
            "raw": response,
        }

    def _unwrap_transaction(self, response: dict) -> dict:
        body = response
        for key in ("data", "transaction"):
            nested = response.get(key)
            if isinstance(nested, dict) and nested:
                body = nested
                break
        return body

    def _normalize_transaction(self, body: dict, fallback_id: str = "") -> dict:
        status = body.get("status") or body.get("statut") or body.get("state") or ""
        return {
            "status": str(status).lower(),
            "amount": body.get("amount") if body.get("amount") is not None else body.get("montant"),
            "order_id": body.get("order_id") or body.get("reference") or body.get("ref"),
            "transaction_id": (
                body.get("transaction_id") or body.get("id") or body.get("_id") or fallback_id
            ),
            "raw": body,
        }

    def verify_payment(self, transaction_id: str) -> tuple[bool, dict]:
        """Interroge l'API : seule source de vérité sur le statut et le montant."""
        transaction_id = (transaction_id or "").strip()
        if not transaction_id:
            return False, {"error": "missing transaction id"}
        last_error: dict = {"error": "missing transaction id"}
        for endpoint in (
            f"/v1/transaction/api/{transaction_id}",
            f"/v1/transaction/api/status/{transaction_id}",
            f"/v1/transaction/{transaction_id}",
        ):
            success, response = self._request("GET", endpoint)
            if success:
                body = self._unwrap_transaction(response)
                return True, self._normalize_transaction(body, transaction_id)
            last_error = response
        return False, last_error

    def find_payment_by_reference(self, order_id: str) -> tuple[bool, dict]:
        """Retombe utilisée quand SingPay n'a pas encore renvoyé d'identifiant."""
        order_id = (order_id or "").strip()
        if not order_id:
            return False, {"error": "missing reference"}
        references = [order_id]
        if not order_id.startswith("REF-"):
            references.append(f"REF-{order_id}")
        last_error: dict = {"error": "missing reference"}
        for reference in references:
            success, response = self._request(
                "GET", f"/v1/transaction/api/search/by-reference/{reference}"
            )
            if success:
                body = self._unwrap_transaction(response)
                return True, self._normalize_transaction(body)
            last_error = response
        return False, last_error

    def _signature_candidates(self, raw_body: str, timestamp: str) -> list[str]:
        """
        Variantes de calcul acceptées.

        Le schéma **de référence** est celui éprouvé en production sur
        Gabomazone : ``HMAC-SHA256(secret, timestamp + json_trié_compact)``.
        Les autres variantes (corps brut, sans horodatage) restent acceptées
        au cas où la passerelle changerait de convention.
        """
        secret = self.webhook_secret.encode("utf-8")

        def digest(message: str) -> str:
            return hmac.new(secret, message.encode("utf-8"), hashlib.sha256).hexdigest()

        candidates = []
        try:
            parsed = json.loads(raw_body)
        except (ValueError, TypeError):
            parsed = None
        if parsed is not None:
            # Schéma Gabomazone, en premier.
            canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
            candidates.append(digest(f"{timestamp}{canonical}"))
            candidates.append(digest(canonical))
        candidates.append(digest(f"{timestamp}{raw_body}"))
        candidates.append(digest(raw_body))
        return candidates

    def _timestamp_freshness(self, timestamp: str) -> bool | None:
        """
        ``True`` frais, ``False`` périmé, ``None`` format non reconnu.

        SingPay ne documente pas le format de ``X-Timestamp`` et Gabomazone le
        traite comme une chaîne opaque. On sait donc lire l'epoch (secondes ou
        millisecondes) et l'ISO 8601, mais pas deviner le reste : face à un
        format inconnu, on rend ``None`` plutôt que de rejeter tous les
        webhooks légitimes.
        """
        raw = (timestamp or "").strip()
        if not raw:
            return None

        sent = None
        try:
            sent = float(raw)
        except (TypeError, ValueError):
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            sent = parsed.timestamp()
        else:
            # Horodatage en millisecondes.
            if sent > 1e11:
                sent /= 1000.0

        return abs(time.time() - sent) <= self.tolerance_seconds

    def verify_webhook_signature(self, raw_body: str, signature: str, timestamp: str) -> bool:
        """
        Vrai uniquement si la signature correspond ET l'horodatage est frais.

        ``raw_body`` doit être le corps *exact* reçu : re-sérialiser un dict déjà
        parsé casse la signature et rouvre la porte au contournement.
        """
        signature = (signature or "").strip()
        if not signature or not self.webhook_secret:
            return False

        fresh = self._timestamp_freshness(timestamp)
        if fresh is False:
            logger.warning("%s webhook rejeté : horodatage périmé", LOG_PREFIX)
            return False
        if fresh is None:
            # Format inconnu : on ne bloque pas, mais on le signale pour pouvoir
            # activer SINGPAY_WEBHOOK_REQUIRE_FRESH_TIMESTAMP une fois identifié.
            if getattr(settings, "SINGPAY_WEBHOOK_REQUIRE_FRESH_TIMESTAMP", False):
                logger.warning("%s webhook rejeté : horodatage illisible", LOG_PREFIX)
                return False
            logger.warning(
                "%s horodatage au format non reconnu (%r) : anti-rejeu inactif. "
                "La signature et la revérification API restent appliquées.",
                LOG_PREFIX,
                (timestamp or "")[:40],
            )

        body = raw_body if isinstance(raw_body, str) else json.dumps(raw_body, sort_keys=True)
        for expected in self._signature_candidates(body, (timestamp or "").strip()):
            if hmac.compare_digest(expected, signature):
                return True
        logger.warning("%s webhook rejeté : signature invalide", LOG_PREFIX)
        return False


singpay_service = SingPayService()
