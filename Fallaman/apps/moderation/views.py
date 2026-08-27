from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.ratelimit import rate_limit
from apps.core.redirects import safe_redirect_target
from apps.listings.models import Listing

from .models import BlockedUser, Report


@login_required
@require_http_methods(["GET", "POST"])
@rate_limit("report", limit=15, window_seconds=3600)
def report_listing(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    if request.method == "POST":
        # `choices` n'est pas vérifié à l'enregistrement : sans cette liste
        # blanche, n'importe quelle chaîne atterrirait dans la colonne.
        reason = request.POST.get("reason") or ""
        if reason not in Report.Reason.values:
            reason = Report.Reason.OTHER
        Report.objects.create(
            reporter=request.user,
            listing=listing,
            reported_user=listing.author,
            reason=reason,
            details=(request.POST.get("details") or "")[:2000],
        )
        messages.success(request, "Merci. Notre équipe va examiner ce signalement.")
        return redirect(listing.get_absolute_url())
    return render(
        request,
        "moderation/report.html",
        {"listing": listing, "reasons": Report.Reason.choices},
    )


@login_required
@require_POST
def block_user(request, pk):
    if request.user.pk == pk:
        messages.error(request, "Action impossible.")
        return redirect("core:home")

    User = get_user_model()
    other = get_object_or_404(User, pk=pk)
    BlockedUser.objects.get_or_create(blocker=request.user, blocked=other)
    messages.info(request, f"{other.display_name} ne pourra plus vous écrire.")
    return redirect(
        safe_redirect_target(request.POST.get("next"), "messaging:inbox", request=request)
    )


@login_required
@require_POST
def unblock_user(request, pk):
    if request.user.pk == pk:
        messages.error(request, "Action impossible.")
        return redirect("core:home")

    User = get_user_model()
    other = get_object_or_404(User, pk=pk)
    deleted, _ = BlockedUser.objects.filter(blocker=request.user, blocked=other).delete()
    if deleted:
        messages.success(request, f"{other.display_name} a été débloqué(e).")
    else:
        messages.info(request, "Cette personne n'était pas dans vos blocages.")
    return redirect(
        safe_redirect_target(request.POST.get("next"), "messaging:inbox", request=request)
    )
