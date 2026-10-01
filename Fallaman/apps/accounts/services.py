"""Parcours de connexion Fallaman.

Deux chemins, et deux seulement :

* **Activation** — première connexion, ou mot de passe oublié. Un code à six
  chiffres part par e-mail, puis le membre choisit son mot de passe.
* **Connexion courante** — numéro de téléphone + mot de passe.

Le code n'est donc plus un moyen de connexion, mais un moyen de *poser* un mot
de passe. C'est ce qui permet de n'envoyer qu'un message par compte, au lieu
d'un à chaque visite.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.utils import hash_otp

from .models import PhoneOTP
from .otp_delivery import OTPDeliveryError, deliver
from .phone import normalize_phone

logger = logging.getLogger("apps.accounts")
User = get_user_model()

#: Demandes de code tolérées par numéro sur 10 minutes.
MAX_CODE_REQUESTS = 5


class OTPError(Exception):
    pass


class ActivationBlockedError(OTPError):
    """Le compte existe mais ne peut pas être activé en libre-service."""


# ── Envoi du code ───────────────────────────────────────────────────────


def _resolve_activation_email(user, submitted_email: str) -> str:
    """
    Détermine l'adresse qui recevra le code.

    Règle de sécurité centrale : **pour un compte existant, le code part
    toujours à l'adresse enregistrée**, jamais à celle saisie dans le
    formulaire. Sans cela, quiconque connaît un numéro de téléphone pourrait
    se faire envoyer le code sur sa propre boîte et s'emparer du compte.
    """
    submitted = (submitted_email or "").strip()

    if user is None:
        # Création de compte : l'adresse fournie fait foi.
        if not submitted:
            raise OTPError("Indiquez votre adresse e-mail pour recevoir le code.")
        return submitted

    if user.email:
        return user.email

    # Compte hérité du temps où la connexion se faisait par SMS : aucune
    # adresse au dossier. Accepter celle saisie reviendrait à offrir le compte
    # au premier venu connaissant le numéro.
    raise ActivationBlockedError(
        "Ce compte a été créé avant l'arrivée des mots de passe et n'a pas "
        "d'adresse e-mail enregistrée. Contactez l'équipe Fallaman pour le "
        "réactiver."
    )


def request_activation_code(phone_number: str, email: str = "") -> str:
    """Envoie un code de vérification. Renvoie le code en développement."""
    phone = normalize_phone(phone_number)
    now = timezone.now()

    recent = PhoneOTP.objects.filter(
        phone_number=phone, created_at__gte=now - timedelta(minutes=10), is_used=False
    ).count()
    if recent >= MAX_CODE_REQUESTS:
        raise OTPError("Trop de demandes. Réessayez dans quelques minutes.")

    user = User.objects.filter(phone_number=phone).first()
    if user and not user.is_active:
        raise OTPError("Ce compte a été suspendu.")
    destination = _resolve_activation_email(user, email)

    # Le code fixe de développement ne doit jamais servir ailleurs : il rendrait
    # tous les comptes accessibles avec la même valeur.
    use_dev_code = settings.OTP_PROVIDER == "console" and settings.DEV_CONVENIENCES
    code = settings.OTP_DEV_CODE if use_dev_code else _generate_code()

    otp = PhoneOTP.objects.create(
        phone_number=phone,
        code_hash=hash_otp(phone, code, settings.SECRET_KEY),
        expires_at=now + timedelta(seconds=settings.OTP_CODE_TTL_SECONDS),
    )
    try:
        _deliver(phone, code, destination)
    except OTPError:
        # Un code jamais remis ne doit pas amputer le quota de l'utilisateur.
        otp.delete()
        raise

    logger.info("Code d'activation envoyé (otp_id=%s).", otp.pk)
    return code if settings.DEV_CONVENIENCES else ""


# ── Vérification du code ────────────────────────────────────────────────


def verify_activation_code(phone_number: str, code: str) -> None:
    """
    Consomme le code. Ne connecte personne : le mot de passe reste à choisir.

    Lève ``OTPError`` si le code est faux, périmé, ou trop de fois tenté.
    """
    phone = normalize_phone(phone_number)
    otp = (
        PhoneOTP.objects.filter(phone_number=phone, is_used=False)
        .order_by("-created_at")
        .first()
    )
    if not otp:
        raise OTPError("Code incorrect. Réessayez.")
    if timezone.now() > otp.expires_at:
        raise OTPError("Ce code a expiré. Demandez-en un nouveau.")
    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise OTPError("Trop de tentatives. Demandez un nouveau code.")

    expected = hash_otp(phone, (code or "").strip(), settings.SECRET_KEY)
    if expected != otp.code_hash:
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        raise OTPError("Code incorrect. Réessayez.")

    otp.is_used = True
    otp.save(update_fields=["is_used"])


# ── Pose du mot de passe ────────────────────────────────────────────────


def complete_activation(request, phone_number: str, email: str, password: str):
    """
    Crée ou met à jour le compte, pose le mot de passe, puis connecte.

    Renvoie ``(user, created)`` : l'appelant a besoin de distinguer une
    première connexion d'une simple réinitialisation de mot de passe pour
    choisir où emmener la personne ensuite.
    """
    phone = normalize_phone(phone_number)

    with transaction.atomic():
        user = User.objects.select_for_update().filter(phone_number=phone).first()
        created = user is None
        if created:
            user = User(phone_number=phone, is_active=True)

        if not user.is_active:
            raise OTPError("Ce compte a été suspendu.")

        # Sur un compte existant, l'adresse au dossier ne bouge pas : la
        # changer ici déplacerait la cible des futurs codes.
        if created:
            user.email = (email or "").strip()
        user.email_verified = bool(user.email)

        # Le téléphone n'est plus vérifié par l'envoi du code — il l'est par
        # l'équipe depuis le tableau de bord. Ne pas le prétendre ici.
        validate_password(password, user=user)
        user.set_password(password)
        user.save()

    login(request, user, backend="apps.accounts.backends.PhoneModelBackend")
    logger.info("Compte activé (created=%s).", created)
    return user, created


# ── Connexion courante ──────────────────────────────────────────────────


def login_with_password(request, phone_number: str, password: str):
    """Connexion téléphone + mot de passe. Lève ``OTPError`` si refusée."""
    try:
        phone = normalize_phone(phone_number)
    except ValidationError as exc:
        raise OTPError("Ce numéro de téléphone n'est pas valide.") from exc

    user = authenticate(request, username=phone, password=password)
    if user is None:
        # Message unique : ne pas révéler si le numéro est connu.
        raise OTPError("Numéro ou mot de passe incorrect.")

    login(request, user, backend="apps.accounts.backends.PhoneModelBackend")
    return user


def needs_activation(phone_number: str) -> bool:
    """Vrai si ce numéro n'a pas encore de mot de passe utilisable."""
    try:
        phone = normalize_phone(phone_number)
    except ValidationError:
        return False
    user = User.objects.filter(phone_number=phone).first()
    return bool(user and not user.has_usable_password())


# ── Interne ─────────────────────────────────────────────────────────────


def _generate_code() -> str:
    from django.utils.crypto import get_random_string

    return get_random_string(6, allowed_chars="0123456789")


def _deliver(phone: str, code: str, email: str) -> None:
    """Délègue au canal configuré ; les échecs remontent en OTPError."""
    try:
        deliver(phone, code, email)
    except OTPDeliveryError as exc:
        raise OTPError(str(exc)) from exc
