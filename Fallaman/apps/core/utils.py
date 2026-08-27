import hashlib
import re
import unicodedata
from datetime import datetime

from django.utils import timezone


def strip_accents(value: str) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_text(value: str) -> str:
    text = strip_accents(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def format_fcfa(amount) -> str:
    if amount is None:
        return "À discuter"
    try:
        number = int(amount)
    except (TypeError, ValueError):
        return "À discuter"
    formatted = f"{number:,}".replace(",", " ")
    return f"{formatted} FCFA"


def relative_date(value: datetime | None) -> str:
    if not value:
        return ""
    now = timezone.now()
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    delta = now - value
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "À l'instant"
    if seconds < 3600:
        minutes = seconds // 60
        return f"Il y a {minutes} min"
    if seconds < 86400:
        hours = seconds // 3600
        return f"Il y a {hours} h"
    if seconds < 172800:
        return "Hier"
    if seconds < 604800:
        days = seconds // 86400
        return f"Il y a {days} jours"
    return value.astimezone(timezone.get_current_timezone()).strftime("%d %B %Y")


def hash_otp(phone: str, code: str, secret: str) -> str:
    payload = f"{phone}:{code}:{secret}"
    return hashlib.sha256(payload.encode()).hexdigest()


SUSPICIOUS_MONEY_PATTERNS = [
    r"envoyez?\s+\d",
    r"frais\s+d['’]?inscription",
    r"payer?\s+pour\s+(obtenir|avoir|l['’]?emploi)",
    r"depot\s+prealable",
    r"dépôt\s+préalable",
    r"western\s+union",
    r"moneygram",
    r"airtel\s+money.{0,20}inscription",
]


def looks_like_money_request(text: str) -> bool:
    haystack = normalize_text(text)
    raw = (text or "").lower()
    for pattern in SUSPICIOUS_MONEY_PATTERNS:
        if re.search(pattern, raw, re.IGNORECASE):
            return True
        if re.search(normalize_text(pattern.replace(r"\s+", " ")), haystack):
            return True
    return False


def contains_suspicious_link(text: str) -> bool:
    return bool(re.search(r"https?://|\bwww\.|\.bit\.ly|\btinyurl\b", text or "", re.IGNORECASE))
