from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.notifications.services import notify, notify_recommendation

from .models import Listing, SearchAlert
from .services import search_listings, users_to_notify_for_listing


@shared_task
def expire_listings():
    now = timezone.now()
    qs = Listing.objects.filter(status=Listing.Status.PUBLISHED, expires_at__lte=now)
    count = 0
    for listing in qs:
        listing.status = Listing.Status.EXPIRED
        listing.save(update_fields=["status", "updated_at"])
        notify(
            listing.author,
            "listing_expired",
            f"Votre annonce « {listing.title} » a expiré.",
            url=listing.get_absolute_url(),
        )
        count += 1
    return count


@shared_task
def send_search_alerts():
    now = timezone.now()
    sent = 0
    for alert in SearchAlert.objects.filter(is_active=True).select_related("user", "profession", "city"):
        qs = Listing.objects.published()
        if alert.query:
            qs = search_listings(qs, alert.query)
        if alert.profession_id:
            qs = qs.filter(profession_id=alert.profession_id)
        if alert.city_id:
            qs = qs.filter(city_id=alert.city_id)
        if alert.listing_type:
            qs = qs.filter(listing_type=alert.listing_type)
        if alert.last_sent_at:
            qs = qs.filter(published_at__gt=alert.last_sent_at)
        listing = qs.order_by("-published_at").first()
        if listing:
            created = notify_recommendation(alert.user, listing)
            if created:
                sent += 1
            alert.last_sent_at = now
            alert.save(update_fields=["last_sent_at"])
    return sent


@shared_task
def notify_listing_matches(listing_id: int):
    """Notifie dès qu'un poste correspondant à une recherche est mis en ligne."""
    listing = (
        Listing.objects.filter(pk=listing_id, status=Listing.Status.PUBLISHED)
        .select_related("profession", "city")
        .prefetch_related("profession__aliases")
        .first()
    )
    if not listing:
        return 0

    sent = 0
    now = timezone.now()
    for user, alert in users_to_notify_for_listing(listing):
        created = notify_recommendation(user, listing)
        if created:
            sent += 1
        if alert:
            alert.last_sent_at = now
            alert.save(update_fields=["last_sent_at"])
    return sent


@shared_task
def notify_new_listing_matches():
    """Filet de sécurité périodique : annonces récentes non encore notifiées aux matchs."""
    since = timezone.now() - timedelta(hours=1)
    sent = 0
    qs = (
        Listing.objects.published()
        .filter(published_at__gte=since)
        .select_related("profession", "city")
        .order_by("-published_at")[:20]
    )
    for listing in qs:
        sent += notify_listing_matches(listing.pk)
    return sent
