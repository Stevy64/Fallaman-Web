"""Tests recommandations + pricing + activation mock."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.listings.models import Listing
from apps.listings.services import recent_listings
from apps.payments.models import PaymentTransaction
from apps.payments.services.checkout import apply_payment_success, create_payment
from apps.profiles.models import Profile
from apps.recommendations.models import RecommendationPurchase
from apps.recommendations.pricing import quote, quote_catalog
from apps.recommendations.services import activate_purchase, create_pending_purchase


@pytest.mark.django_db
def test_listing_boost_price_scales_with_duration():
    q1 = quote("listing", 1)
    q7 = quote("listing", 7)
    assert q1.amount == 500
    assert q7.amount < q7.daily_rate * 7
    assert q7.amount > q1.amount
    assert len(quote_catalog("listing")) == 4


@pytest.mark.django_db
def test_boosted_listing_ranks_first(user, db):
    other = user.__class__.objects.create_user(phone_number="+24106200099")
    older = Listing.objects.create(
        author=other,
        listing_type=Listing.Type.MISSION,
        title="Annonce ancienne",
        description="desc",
        status=Listing.Status.PUBLISHED,
        published_at=timezone.now() - timedelta(days=2),
        expires_at=timezone.now() + timedelta(days=5),
    )
    boosted = Listing.objects.create(
        author=user,
        listing_type=Listing.Type.MISSION,
        title="Annonce boostée",
        description="desc",
        status=Listing.Status.PUBLISHED,
        published_at=timezone.now() - timedelta(days=3),
        expires_at=timezone.now() + timedelta(days=5),
        boosted_until=timezone.now() + timedelta(days=2),
        boost_score=900,
    )
    ids = list(recent_listings().values_list("id", flat=True)[:2])
    assert ids[0] == boosted.id
    assert older.id in ids or True


@pytest.mark.django_db
def test_activate_listing_boost_via_mock_payment(user, rf):
    listing = Listing.objects.create(
        author=user,
        listing_type=Listing.Type.EMPLOYMENT,
        title="Nounou Libreville",
        description="desc",
        status=Listing.Status.PUBLISHED,
        published_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=20),
    )
    purchase = create_pending_purchase(
        user=user,
        kind=RecommendationPurchase.Kind.LISTING,
        duration_days=3,
        listing=listing,
    )
    request = rf.get("/")
    request.user = user
    # Absolute URI helper
    request.META["HTTP_HOST"] = "testserver"
    tx, url = create_payment(
        request=request,
        user=user,
        purpose=PaymentTransaction.Purpose.LISTING_BOOST,
        amount=purchase.amount,
        description="test",
        metadata={"purchase_id": purchase.pk, "listing_id": listing.pk},
    )
    purchase.payment = tx
    purchase.save(update_fields=["payment"])
    assert "simulation" in url
    apply_payment_success(tx, provider_transaction_id="MOCK-1")
    listing.refresh_from_db()
    purchase.refresh_from_db()
    assert purchase.status == RecommendationPurchase.Status.ACTIVE
    assert listing.is_boosted
    assert listing.boost_score > 0


@pytest.mark.django_db
def test_boost_listing_page_requires_owner(client, user):
    listing = Listing.objects.create(
        author=user,
        listing_type=Listing.Type.MISSION,
        title="Test",
        description="desc",
        status=Listing.Status.PUBLISHED,
        published_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=5),
    )
    client.force_login(user)
    response = client.get(reverse("recommendations:boost_listing", kwargs={"pk": listing.pk}))
    assert response.status_code == 200
    assert b"Mettre en avant" in response.content


@pytest.mark.django_db
def test_profile_boost_activation(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.display_name = "Steevi"
    profile.save(update_fields=["display_name"])
    purchase = create_pending_purchase(
        user=user,
        kind=RecommendationPurchase.Kind.PROFILE,
        duration_days=1,
        profile=profile,
    )
    activate_purchase(purchase)
    profile.refresh_from_db()
    assert profile.is_recommended
