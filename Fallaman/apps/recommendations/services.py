"""Activation, ranking et diffusion des recommandations payantes."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.urls import reverse
from django.utils import timezone

from apps.listings.models import Listing
from apps.notifications.services import notify
from apps.payments.models import PaymentTransaction
from apps.profiles.models import Profile
from apps.recommendations.models import CandidateIntroduction, RecommendationPurchase
from apps.recommendations.pricing import quote

logger = logging.getLogger(__name__)


def compute_boost_score(*, amount: int, duration_days: int, ends_at) -> int:
    """
    Score de ranking :
    - montant payé (engagement)
    - durée restante (fraîcheur de la mise en avant)
    - bonus durée achetée (engagement long terme)
    """
    now = timezone.now()
    remaining_h = max(0, int((ends_at - now).total_seconds() // 3600)) if ends_at else 0
    return int(amount) + (duration_days * 25) + remaining_h


def create_pending_purchase(*, user, kind: str, duration_days: int, listing=None, profile=None):
    price = quote(kind, duration_days)
    return RecommendationPurchase.objects.create(
        user=user,
        kind=kind,
        listing=listing,
        profile=profile,
        duration_days=price.duration_days,
        amount=price.amount,
        daily_rate=price.daily_rate,
        discount_percent=price.discount_percent,
        status=RecommendationPurchase.Status.PENDING,
    )


@transaction.atomic
def activate_purchase(purchase: RecommendationPurchase) -> RecommendationPurchase:
    now = timezone.now()
    duration = timedelta(days=purchase.duration_days)

    if purchase.kind == RecommendationPurchase.Kind.LISTING and purchase.listing_id:
        listing = Listing.objects.select_for_update().get(pk=purchase.listing_id)
        base = listing.boosted_until if listing.boosted_until and listing.boosted_until > now else now
        ends = base + duration
        score = compute_boost_score(
            amount=purchase.amount,
            duration_days=purchase.duration_days,
            ends_at=ends,
        )
        listing.boosted_until = ends
        listing.boost_score = max(listing.boost_score or 0, score)
        listing.save(update_fields=["boosted_until", "boost_score", "updated_at"])
        purchase.starts_at = now
        purchase.ends_at = ends
        purchase.score = score
        purchase.status = RecommendationPurchase.Status.ACTIVE
        purchase.save(
            update_fields=["starts_at", "ends_at", "score", "status", "updated_at"]
        )
        _notify_seekers_for_boosted_listing(listing)
        purchase.notified_at = timezone.now()
        purchase.save(update_fields=["notified_at", "updated_at"])
        _alert_staff_recommendation(purchase)
        return purchase

    if purchase.kind == RecommendationPurchase.Kind.PROFILE and purchase.profile_id:
        profile = Profile.objects.select_for_update().get(pk=purchase.profile_id)
        base = (
            profile.recommended_until
            if profile.recommended_until and profile.recommended_until > now
            else now
        )
        ends = base + duration
        score = compute_boost_score(
            amount=purchase.amount,
            duration_days=purchase.duration_days,
            ends_at=ends,
        )
        profile.recommended_until = ends
        profile.recommend_score = max(profile.recommend_score or 0, score)
        profile.save(update_fields=["recommended_until", "recommend_score", "updated_at"])
        purchase.starts_at = now
        purchase.ends_at = ends
        purchase.score = score
        purchase.status = RecommendationPurchase.Status.ACTIVE
        purchase.save(
            update_fields=["starts_at", "ends_at", "score", "status", "updated_at"]
        )
        _notify_employers_for_recommended_profile(profile)
        purchase.notified_at = timezone.now()
        purchase.save(update_fields=["notified_at", "updated_at"])
        _alert_staff_recommendation(purchase)
        return purchase

    purchase.status = RecommendationPurchase.Status.CANCELLED
    purchase.save(update_fields=["status", "updated_at"])
    return purchase


def activate_purchase_for_payment(tx: PaymentTransaction) -> RecommendationPurchase | None:
    purchase = getattr(tx, "recommendation_purchase", None)
    if purchase is None:
        purchase = RecommendationPurchase.objects.filter(payment=tx).first()
    if not purchase:
        # Reconstitute from metadata if needed
        meta = tx.metadata or {}
        purchase_id = meta.get("purchase_id")
        if purchase_id:
            purchase = RecommendationPurchase.objects.filter(pk=purchase_id).first()
    if not purchase:
        logger.warning("No recommendation purchase for payment %s", tx.reference)
        return None
    if purchase.status == RecommendationPurchase.Status.ACTIVE:
        return purchase
    purchase.payment = tx
    purchase.save(update_fields=["payment", "updated_at"])
    return activate_purchase(purchase)


def with_boost_ranking(queryset, sort: str = "recent"):
    """Priorise les annonces boostées actives, puis score, puis récence."""
    now = timezone.now()
    qs = queryset.annotate(
        boost_active=Case(
            When(boosted_until__gt=now, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    )
    if sort == "salary":
        return qs.order_by("-boost_active", "-salary_amount", "-published_at")
    return qs.order_by("-boost_active", "-boost_score", "-published_at")


def introductions_for_listing(listing: Listing, limit: int = 12):
    """Intros à afficher côté pourvoyeur (hors refusés)."""
    now = timezone.now()
    # Synchronise d'éventuels profils encore actifs non proposés.
    for profile in recommended_profiles_for_listing(listing, limit=limit):
        CandidateIntroduction.objects.get_or_create(
            listing=listing,
            profile=profile,
            defaults={"employer_id": listing.author_id},
        )
    return list(
        CandidateIntroduction.objects.filter(listing=listing)
        .exclude(status=CandidateIntroduction.Status.DECLINED)
        .filter(
            Q(profile__recommended_until__gt=now)
            | Q(status=CandidateIntroduction.Status.ACCEPTED)
        )
        .select_related(
            "profile",
            "profile__user",
            "profile__city",
            "profile__primary_profession",
        )
        .order_by("-created_at")[:limit]
    )


def decide_introduction(intro: CandidateIntroduction, *, accept: bool) -> CandidateIntroduction:
    intro.status = (
        CandidateIntroduction.Status.ACCEPTED
        if accept
        else CandidateIntroduction.Status.DECLINED
    )
    intro.decided_at = timezone.now()
    intro.save(update_fields=["status", "decided_at", "updated_at"])
    return intro


def _alert_staff_recommendation(purchase: RecommendationPurchase):
    from apps.core.utils import format_fcfa
    from apps.notifications.models import Notification
    from apps.notifications.services import notify_staff

    label = purchase.get_kind_display()
    notify_staff(
        Notification.Kind.STAFF_RECOMMENDATION,
        f"{label} · {format_fcfa(purchase.amount)} · {purchase.duration_days} j",
        url=reverse("dashboard:recommendations"),
    )


def recommended_profiles_for_listing(listing: Listing, limit: int = 6):
    """Candidats payants recommandés auprès d'un pourvoyeur d'offre."""
    now = timezone.now()
    qs = (
        Profile.objects.filter(
            is_public=True,
            recommended_until__gt=now,
        )
        .exclude(user_id=listing.author_id)
        .select_related("user", "city", "primary_profession")
    )
    filters = Q()
    has_filter = False
    if listing.profession_id:
        has_filter = True
        filters |= Q(primary_profession_id=listing.profession_id)
        category_id = getattr(listing.profession, "category_id", None)
        if category_id:
            filters |= Q(primary_profession__category_id=category_id)
    if listing.city_id:
        has_filter = True
        filters |= Q(city_id=listing.city_id)
    if listing.custom_profession:
        has_filter = True
        filters |= Q(looking_for__icontains=listing.custom_profession)
        filters |= Q(primary_profession__name__icontains=listing.custom_profession)

    matched = qs.filter(filters) if has_filter else qs
    if has_filter and not matched.exists():
        matched = qs
    return list(matched.order_by("-recommend_score", "-updated_at")[:limit])


def _notify_seekers_for_boosted_listing(listing: Listing):
    from apps.listings.services import users_to_notify_for_listing
    from apps.notifications.models import Notification
    from apps.notifications.services import notify_recommendation

    for user, _alert in users_to_notify_for_listing(listing):
        notify_recommendation(user, listing)
        notify(
            user,
            Notification.Kind.BOOSTED_LISTING,
            f"Annonce mise en avant : {listing.job_label} à {listing.location_label}",
            url=listing.get_absolute_url(),
        )


def _notify_employers_for_recommended_profile(profile: Profile):
    from apps.notifications.models import Notification

    qs = Listing.objects.published().exclude(author_id=profile.user_id)
    filters = Q()
    has_filter = False
    if profile.primary_profession_id:
        has_filter = True
        filters |= Q(profession_id=profile.primary_profession_id)
        category_id = getattr(profile.primary_profession, "category_id", None)
        if category_id:
            filters |= Q(profession__category_id=category_id)
    if profile.city_id:
        has_filter = True
        filters |= Q(city_id=profile.city_id)
    if profile.looking_for:
        has_filter = True
        filters |= (
            Q(title__icontains=profile.looking_for)
            | Q(custom_profession__icontains=profile.looking_for)
        )

    base = qs.filter(filters) if has_filter else qs
    listings = list(base.select_related("author").order_by("-published_at")[:25])
    name = profile.display_name or "Un Fallaman"
    job = (
        profile.primary_profession.name
        if profile.primary_profession_id
        else (profile.looking_for or "un poste")
    )
    for listing in listings:
        CandidateIntroduction.objects.get_or_create(
            listing=listing,
            profile=profile,
            defaults={"employer_id": listing.author_id},
        )
        notify(
            listing.author,
            Notification.Kind.RECOMMENDED_CANDIDATE,
            f"{name} se recommande pour « {listing.title} » ({job})",
            url=listing.get_absolute_url(),
        )


def expire_recommendations() -> int:
    now = timezone.now()
    expired = RecommendationPurchase.objects.filter(
        status=RecommendationPurchase.Status.ACTIVE,
        ends_at__lte=now,
    )
    count = expired.update(status=RecommendationPurchase.Status.EXPIRED)

    Listing.objects.filter(boosted_until__lte=now, boost_score__gt=0).update(boost_score=0)
    Profile.objects.filter(recommended_until__lte=now, recommend_score__gt=0).update(
        recommend_score=0
    )
    return count


def listing_is_boosted(listing: Listing) -> bool:
    return bool(listing.boosted_until and listing.boosted_until > timezone.now())


def profile_is_recommended(profile: Profile) -> bool:
    return bool(profile.recommended_until and profile.recommended_until > timezone.now())
