from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.phone import contact_whatsapp_url
from apps.listings.models import Listing
from apps.messaging.models import Conversation, Message
from apps.notifications.services import notify
from apps.payments.models import PaymentTransaction
from apps.payments.services.checkout import create_payment
from apps.profiles.models import Profile
from apps.recommendations.models import CandidateIntroduction, RecommendationPurchase
from apps.recommendations.pricing import quote, quote_catalog
from apps.recommendations.services import (
    create_pending_purchase,
    decide_introduction,
    listing_is_boosted,
    profile_is_recommended,
)


@login_required
@require_http_methods(["GET", "POST"])
def boost_listing(request, pk):
    listing = get_object_or_404(Listing, pk=pk, author=request.user)
    if listing.status != Listing.Status.PUBLISHED:
        messages.error(request, "Seules les annonces publiées peuvent être mises en avant.")
        return redirect(listing.get_absolute_url())

    quotes = quote_catalog(RecommendationPurchase.Kind.LISTING)
    if request.method == "POST":
        try:
            days = int(request.POST.get("duration_days") or 0)
            price = quote(RecommendationPurchase.Kind.LISTING, days)
        except (TypeError, ValueError):
            messages.error(request, "Choisissez une durée valide.")
            return redirect("recommendations:boost_listing", pk=listing.pk)

        purchase = create_pending_purchase(
            user=request.user,
            kind=RecommendationPurchase.Kind.LISTING,
            duration_days=price.duration_days,
            listing=listing,
        )
        try:
            tx, payment_url = create_payment(
                request=request,
                user=request.user,
                purpose=PaymentTransaction.Purpose.LISTING_BOOST,
                amount=price.amount,
                description=f"Boost annonce « {listing.title} » — {price.label}",
                metadata={
                    "purchase_id": purchase.pk,
                    "listing_id": listing.pk,
                    "duration_days": price.duration_days,
                },
            )
        except RuntimeError as exc:
            purchase.status = RecommendationPurchase.Status.CANCELLED
            purchase.save(update_fields=["status", "updated_at"])
            messages.error(request, f"Paiement indisponible : {exc}")
            return redirect("recommendations:boost_listing", pk=listing.pk)

        purchase.payment = tx
        purchase.save(update_fields=["payment", "updated_at"])
        return redirect(payment_url)

    return render(
        request,
        "recommendations/boost_listing.html",
        {
            "listing": listing,
            "quotes": quotes,
            "is_boosted": listing_is_boosted(listing),
            "boosted_until": listing.boosted_until,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def boost_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not profile.is_complete:
        messages.info(
            request,
            "Complétez votre profil (nom, ville, métier) avant de booster sa visibilité.",
        )
        return redirect("profiles:mine")

    quotes = quote_catalog(RecommendationPurchase.Kind.PROFILE)
    if request.method == "POST":
        try:
            days = int(request.POST.get("duration_days") or 0)
            price = quote(RecommendationPurchase.Kind.PROFILE, days)
        except (TypeError, ValueError):
            messages.error(request, "Choisissez une durée valide.")
            return redirect("recommendations:boost_profile")

        purchase = create_pending_purchase(
            user=request.user,
            kind=RecommendationPurchase.Kind.PROFILE,
            duration_days=price.duration_days,
            profile=profile,
        )
        try:
            tx, payment_url = create_payment(
                request=request,
                user=request.user,
                purpose=PaymentTransaction.Purpose.PROFILE_BOOST,
                amount=price.amount,
                description=f"Boost profil — {price.label}",
                metadata={
                    "purchase_id": purchase.pk,
                    "profile_id": profile.pk,
                    "duration_days": price.duration_days,
                },
            )
        except RuntimeError as exc:
            purchase.status = RecommendationPurchase.Status.CANCELLED
            purchase.save(update_fields=["status", "updated_at"])
            messages.error(request, f"Paiement indisponible : {exc}")
            return redirect("recommendations:boost_profile")

        purchase.payment = tx
        purchase.save(update_fields=["payment", "updated_at"])
        return redirect(payment_url)

    return render(
        request,
        "recommendations/boost_profile.html",
        {
            "profile": profile,
            "quotes": quotes,
            "is_recommended": profile_is_recommended(profile),
            "recommended_until": profile.recommended_until,
        },
    )


@login_required
def my_recommendations(request):
    purchases = (
        RecommendationPurchase.objects.filter(user=request.user)
        .select_related("listing", "profile", "payment")
        .order_by("-created_at")[:30]
    )
    return render(
        request,
        "recommendations/mine.html",
        {"purchases": purchases},
    )


@login_required
@require_POST
def candidate_decide(request, pk, action):
    intro = get_object_or_404(
        CandidateIntroduction.objects.select_related("listing", "profile", "profile__user"),
        pk=pk,
        employer=request.user,
    )
    listing = intro.listing
    if action == "accept":
        decide_introduction(intro, accept=True)
        messages.success(
            request,
            f"Vous avez accepté {intro.profile.display_name}. Vous pouvez discuter ou continuer sur WhatsApp.",
        )
    elif action == "decline":
        decide_introduction(intro, accept=False)
        messages.info(request, "Candidat refusé. Il n'apparaîtra plus sur cette annonce.")
    else:
        messages.error(request, "Action inconnue.")
    return redirect(listing.get_absolute_url())


@login_required
@require_POST
def candidate_contact(request, pk):
    """Démarre la discussion après acceptation (et optionnellement ouvre WhatsApp)."""
    intro = get_object_or_404(
        CandidateIntroduction.objects.select_related("listing", "profile", "profile__user"),
        pk=pk,
        employer=request.user,
        status=CandidateIntroduction.Status.ACCEPTED,
    )
    candidate_user = intro.profile.user
    conversation = Conversation.objects.get_or_create_for(
        intro.listing, request.user, candidate_user
    )
    if not conversation.messages.exists():
        Message.objects.create(
            conversation=conversation,
            sender=request.user,
            body=(
                f"Bonjour {intro.profile.display_name or ''}, "
                f"votre profil recommandé m'intéresse pour « {intro.listing.title} »."
            ).strip(),
        )
        conversation.touch()
        notify(
            candidate_user,
            "new_message",
            f"{request.user.display_name} a accepté votre recommandation.",
            url=conversation.get_absolute_url(),
        )
    channel = request.POST.get("channel") or "chat"
    if channel == "whatsapp":
        text = (
            f"Bonjour, je vous contacte suite à votre recommandation sur Fallaman "
            f"pour l'annonce « {intro.listing.title} »."
        )
        wa = contact_whatsapp_url(candidate_user, text=text)
        if wa:
            return redirect(wa)
    return redirect(conversation.get_absolute_url())
