import phonenumbers
from django.core.exceptions import ValidationError


DEFAULT_REGION = "GA"


def normalize_phone(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        raise ValidationError("Indiquez un numéro de téléphone.")
    try:
        parsed = phonenumbers.parse(raw, DEFAULT_REGION)
    except phonenumbers.NumberParseException as exc:
        raise ValidationError("Ce numéro de téléphone n'est pas valide.") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise ValidationError("Ce numéro de téléphone n'est pas valide.")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def whatsapp_digits(value: str) -> str:
    normalized = normalize_phone(value)
    return normalized.replace("+", "")


def build_whatsapp_url(phone: str, text: str = "") -> str:
    """Construit https://wa.me/<numéro> avec le numéro fourni (jamais sans destinataire)."""
    from urllib.parse import quote

    digits = whatsapp_digits(phone)
    if not digits:
        raise ValidationError("Numéro WhatsApp manquant.")
    url = f"https://wa.me/{digits}"
    message = (text or "").strip()
    if message:
        url = f"{url}?text={quote(message)}"
    return url


def contact_whatsapp_url(user, text: str = "") -> str:
    """
    Lien WhatsApp vers le numéro de contact de l'utilisateur.
    Priorité : profile.whatsapp_number si autorisé, sinon téléphone du compte.
    """
    profile = getattr(user, "profile", None)
    if not profile or not profile.show_whatsapp:
        return ""
    raw = (profile.whatsapp_number or "").strip() or (getattr(user, "phone_number", "") or "").strip()
    if not raw:
        return ""
    try:
        return build_whatsapp_url(raw, text=text)
    except ValidationError:
        return ""
