from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.ratelimit import rate_limit
from apps.core.redirects import safe_redirect_target

from .forms import (
    ActivationForm,
    ChoosePasswordForm,
    LoginForm,
    OTPForm,
    StaffPasswordForm,
)
from .services import (
    ActivationBlockedError,
    OTPError,
    complete_activation,
    login_with_password,
    needs_activation,
    request_activation_code,
    verify_activation_code,
)

#: Clé de session portant l'activation en cours.
ACTIVATION_SESSION_KEY = "activation"


def _pending_activation(request) -> dict | None:
    data = request.session.get(ACTIVATION_SESSION_KEY)
    if isinstance(data, dict) and data.get("phone"):
        return data
    return None


@require_http_methods(["GET", "POST"])
@rate_limit("login", limit=15, window_seconds=600)
def login_view(request):
    """Connexion courante : numéro de téléphone + mot de passe."""
    if request.user.is_authenticated:
        return redirect("core:home")

    form = LoginForm(request.POST or None, initial={"next": request.GET.get("next", "")})
    if request.method == "POST" and form.is_valid():
        phone = form.cleaned_data["phone_number"]
        try:
            login_with_password(request, phone, form.cleaned_data["password"])
        except OTPError as exc:
            form.add_error(None, str(exc))
            # Compte sans mot de passe : orienter vers l'activation plutôt que
            # de laisser l'utilisateur buter sur un message générique.
            if needs_activation(phone):
                messages.info(
                    request,
                    "Ce compte n'a pas encore de mot de passe. "
                    "Utilisez « Première connexion » pour en choisir un.",
                )
        else:
            messages.success(request, "Connexion réussie. Bienvenue sur Fallaman.")
            return redirect(
                safe_redirect_target(
                    form.cleaned_data.get("next"), "core:home", request=request
                )
            )
    return render(request, "accounts/login.html", {"form": form})


@require_http_methods(["GET", "POST"])
@rate_limit("activation_request", limit=8, window_seconds=600)
def activate_view(request):
    """Première connexion ou mot de passe oublié : envoi du code par e-mail."""
    if request.user.is_authenticated:
        return redirect("core:home")

    form = ActivationForm(request.POST or None, initial={"next": request.GET.get("next", "")})
    if request.method == "POST" and form.is_valid():
        phone = form.cleaned_data["phone_number"]
        email = form.cleaned_data["email"]
        try:
            code = request_activation_code(phone, email)
        except ActivationBlockedError as exc:
            form.add_error(None, str(exc))
        except OTPError as exc:
            form.add_error("email" if "adresse" in str(exc).lower() else None, str(exc))
        else:
            request.session[ACTIVATION_SESSION_KEY] = {
                "phone": phone,
                "email": email,
                "verified": False,
                "next": form.cleaned_data.get("next") or "",
            }
            if code:
                messages.info(request, f"Mode développement : votre code est {code}.")
            return redirect("accounts:verify")
    return render(request, "accounts/activate.html", {"form": form})


@require_http_methods(["GET", "POST"])
@rate_limit("activation_verify", limit=12, window_seconds=600)
def verify_view(request):
    """Saisie du code reçu. Ne connecte pas : le mot de passe suit."""
    pending = _pending_activation(request)
    if not pending:
        return redirect("accounts:activate")

    form = OTPForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            verify_activation_code(pending["phone"], form.cleaned_data["code"])
        except OTPError as exc:
            form.add_error("code", str(exc))
        else:
            pending["verified"] = True
            request.session[ACTIVATION_SESSION_KEY] = pending
            return redirect("accounts:set_password")
    return render(request, "accounts/verify.html", {"form": form, "email": pending.get("email")})


@require_http_methods(["GET", "POST"])
def set_password_view(request):
    """Choix du mot de passe, une fois le code validé."""
    pending = _pending_activation(request)
    if not pending or not pending.get("verified"):
        return redirect("accounts:activate")

    form = ChoosePasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            complete_activation(
                request,
                pending["phone"],
                pending.get("email", ""),
                form.cleaned_data["password1"],
            )
        except DjangoValidationError as exc:
            for message in exc.messages:
                form.add_error("password1", message)
        except OTPError as exc:
            form.add_error(None, str(exc))
        else:
            target = pending.get("next") or ""
            request.session.pop(ACTIVATION_SESSION_KEY, None)
            messages.success(
                request,
                "Mot de passe enregistré. Utilisez-le pour vos prochaines connexions.",
            )
            return redirect(safe_redirect_target(target, "core:home", request=request))
    return render(request, "accounts/set_password.html", {"form": form})


@require_http_methods(["GET", "POST"])
def staff_login_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("dashboard:home")
    initial = {"next": request.GET.get("next", "")}
    if settings.DEV_CONVENIENCES:
        initial["phone_number"] = DEMO_STAFF_PHONE
    form = StaffPasswordForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data["phone_number"],
            password=form.cleaned_data["password"],
        )
        if (
            user is None
            and settings.DEV_CONVENIENCES
            and DEMO_STAFF_PASSWORD
            and form.cleaned_data["phone_number"] == DEMO_STAFF_PHONE
            and form.cleaned_data["password"] == DEMO_STAFF_PASSWORD
        ):
            user = ensure_demo_staff_user()
        if user is None or not user.is_staff:
            form.add_error(
                None,
                "Téléphone ou mot de passe incorrect, ou compte non autorisé.",
            )
        else:
            login(request, user, backend="apps.accounts.backends.PhoneModelBackend")
            messages.success(request, "Connexion équipe réussie.")
            return redirect(
                safe_redirect_target(
                    form.cleaned_data.get("next"), "dashboard:home", request=request
                )
            )
    return render(
        request,
        "accounts/staff_login.html",
        {
            "form": form,
            "dev_hint": settings.DEV_CONVENIENCES,
        },
    )


#: Compte de démonstration local. Configurable par variables d'environnement
#: pour qu'aucun identifiant exploitable ne vive dans le dépôt.
DEMO_STAFF_PHONE = getattr(settings, "DEMO_STAFF_PHONE", "+24106111111")
DEMO_STAFF_PASSWORD = getattr(settings, "DEMO_STAFF_PASSWORD", "")


def ensure_demo_staff_user():
    """Crée ou répare le compte admin local. Interdit hors développement."""
    if not settings.DEV_CONVENIENCES:
        raise Http404
    if not DEMO_STAFF_PASSWORD:
        raise Http404
    User = get_user_model()
    user, _created = User.objects.get_or_create(
        phone_number=DEMO_STAFF_PHONE,
        defaults={"phone_verified": True, "is_active": True},
    )
    user.phone_verified = True
    user.is_active = True
    user.is_staff = True
    user.is_superuser = True
    user.set_password(DEMO_STAFF_PASSWORD)
    user.save()
    return user


@require_POST
def staff_demo_login_view(request):
    """Connexion one-click du compte admin, uniquement en développement."""
    if not settings.DEV_CONVENIENCES:
        return redirect("accounts:staff_login")
    user = ensure_demo_staff_user()
    login(request, user, backend="apps.accounts.backends.PhoneModelBackend")
    messages.success(request, "Connecté avec le compte démo.")
    return redirect("dashboard:home")


@require_http_methods(["POST", "GET"])
def logout_view(request):
    logout(request)
    messages.info(request, "Vous êtes déconnecté.")
    return redirect("core:home")
