"""Acheminement du code OTP vers l'utilisateur.

Le code ne sert qu'à la *première* connexion et à la réinitialisation du mot
de passe : les connexions suivantes se font par téléphone + mot de passe.
L'adresse e-mail est demandée à l'activation, ce qui en fait le canal par
défaut ; WhatsApp reste disponible pour qui veut le configurer.

Ajouter un canal = écrire une fonction ``(phone, code, email) -> None`` qui
lève ``OTPDeliveryError`` en cas d'échec, puis l'enregistrer dans ``BACKENDS``.
"""

from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger("apps.accounts")


class OTPDeliveryError(Exception):
    """Le code n'a pas pu être remis à l'utilisateur."""


# ── Console (développement) ─────────────────────────────────────────────


def deliver_console(phone: str, code: str, email: str = "") -> None:
    if not getattr(settings, "DEV_CONVENIENCES", False):
        # Sans envoi réel, l'utilisateur ne recevrait jamais son code.
        raise OTPDeliveryError("Aucun fournisseur SMS n'est configuré.")
    logger.info("OTP de développement généré (valeur non journalisée).")
    cible = email or phone
    print(f"[FALLAMAN DEV] Code pour {cible} : {code}")


# ── WhatsApp Cloud API (Meta) ───────────────────────────────────────────


def _whatsapp_settings() -> tuple[str, str, str]:
    phone_number_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "") or ""
    token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "") or ""
    version = getattr(settings, "WHATSAPP_API_VERSION", "v21.0") or "v21.0"
    if not phone_number_id or not token:
        raise OTPDeliveryError(
            "WhatsApp n'est pas configuré (WHATSAPP_PHONE_NUMBER_ID, "
            "WHATSAPP_ACCESS_TOKEN)."
        )
    return phone_number_id, token, version


def _whatsapp_payload(destination: str, code: str) -> dict:
    """
    Construit un message *template* d'authentification.

    Meta n'autorise pas le texte libre en message sortant non sollicité : il
    faut un modèle approuvé de catégorie « Authentication ». Ces modèles
    portent un bouton « copier le code » dont le paramètre doit répéter le
    code — d'où le second composant.
    """
    template = getattr(settings, "WHATSAPP_OTP_TEMPLATE", "otp_code") or "otp_code"
    language = getattr(settings, "WHATSAPP_OTP_LANGUAGE", "fr") or "fr"
    components = [
        {"type": "body", "parameters": [{"type": "text", "text": code}]}
    ]
    if getattr(settings, "WHATSAPP_OTP_HAS_COPY_BUTTON", True):
        components.append(
            {
                "type": "button",
                "sub_type": "url",
                "index": "0",
                "parameters": [{"type": "text", "text": code}],
            }
        )
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": destination,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": language},
            "components": components,
        },
    }


def deliver_whatsapp(phone: str, code: str, email: str = "") -> None:
    phone_number_id, token, version = _whatsapp_settings()
    # L'API attend le numéro international sans le « + ».
    destination = phone.lstrip("+")
    url = f"https://graph.facebook.com/{version}/{phone_number_id}/messages"

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=_whatsapp_payload(destination, code),
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        # Pas de logger.exception : la trace porterait le jeton d'accès.
        detail = ""
        if getattr(exc, "response", None) is not None:
            detail = (exc.response.text or "")[:300]
        logger.warning("Envoi WhatsApp échoué : %s %s", exc, detail)
        raise OTPDeliveryError(
            "Impossible d'envoyer le code par WhatsApp. Réessayez dans un instant."
        ) from exc

    logger.info("Code OTP remis par WhatsApp (message_id inconnu si non renvoyé).")


# ── E-mail ──────────────────────────────────────────────────────────────

OTP_EMAIL_SUBJECT = "Votre code Fallaman"

OTP_EMAIL_BODY = """Bonjour,

Votre code de vérification Fallaman est : {code}

Il expire dans {minutes} minutes. Saisissez-le pour choisir votre mot de passe.

Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : votre
compte reste inchangé tant que le code n'est pas utilisé.

— L'équipe Fallaman
"""


def deliver_email(phone: str, code: str, email: str = "") -> None:
    from django.core.mail import send_mail

    destination = (email or "").strip()
    if not destination:
        raise OTPDeliveryError("Aucune adresse e-mail n'est associée à ce compte.")

    expediteur = getattr(settings, "DEFAULT_FROM_EMAIL", "") or ""
    minutes = max(1, int(getattr(settings, "OTP_CODE_TTL_SECONDS", 300)) // 60)
    try:
        envoyes = send_mail(
            subject=OTP_EMAIL_SUBJECT,
            message=OTP_EMAIL_BODY.format(code=code, minutes=minutes),
            from_email=expediteur or None,
            recipient_list=[destination],
            fail_silently=False,
        )
    except Exception as exc:
        # Pas de logger.exception : la trace peut porter les identifiants SMTP.
        logger.warning("Envoi e-mail du code échoué : %s", exc)
        raise OTPDeliveryError(
            "Impossible d'envoyer le code par e-mail. Réessayez dans un instant."
        ) from exc

    if not envoyes:
        raise OTPDeliveryError(
            "Impossible d'envoyer le code par e-mail. Vérifiez l'adresse saisie."
        )
    logger.info("Code de vérification remis par e-mail.")


# ── Registre ────────────────────────────────────────────────────────────

BACKENDS = {
    "console": deliver_console,
    "email": deliver_email,
    "whatsapp": deliver_whatsapp,
}


def deliver(phone: str, code: str, email: str = "") -> None:
    """Achemine le code via le canal configuré par ``OTP_PROVIDER``."""
    provider = (getattr(settings, "OTP_PROVIDER", "") or "").strip().lower()
    backend = BACKENDS.get(provider)
    if backend is None:
        raise OTPDeliveryError(
            f"Canal d'envoi inconnu : « {provider or 'non défini'} ». "
            f"Valeurs acceptées : {', '.join(sorted(BACKENDS))}."
        )
    backend(phone, code, email)
