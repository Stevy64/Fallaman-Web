from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.listings.models import Listing
from apps.messaging.models import Conversation, Message
from apps.notifications.models import Notification
from apps.profiles.models import Profile
from apps.recommendations.models import CandidateIntroduction, RecommendationPurchase
from apps.recommendations.services import activate_purchase, create_pending_purchase

User = get_user_model()


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        phone_number="06117777", is_staff=True, phone_verified=True
    )


@pytest.mark.django_db
def test_dashboard_recommendations_and_broadcast(client, staff_user, user):
    client.force_login(staff_user)
    assert client.get(reverse("dashboard:recommendations")).status_code == 200
    assert client.get(reverse("dashboard:staff_messaging")).status_code == 200
    assert client.get(reverse("dashboard:staff_messaging") + "?tab=diffusions").status_code == 200
    assert client.get(reverse("dashboard:alerts")).status_code == 200
    response = client.post(
        reverse("dashboard:staff_messaging") + "?tab=diffusions",
        {"title": "Info", "body": "Bonjour à tous", "audience": "active"},
    )
    assert response.status_code == 302
    assert Notification.objects.filter(
        user=user,
        kind=Notification.Kind.STAFF_BROADCAST,
        title__startswith="Info",
    ).exists()


@pytest.mark.django_db
def test_staff_broadcast_to_one_person(client, staff_user, user, other):
    client.force_login(staff_user)
    response = client.post(
        reverse("dashboard:staff_messaging") + "?tab=diffusions",
        {
            "title": "Privé",
            "body": "Message ciblé",
            "audience": "one",
            "recipient_id": str(user.pk),
        },
    )
    assert response.status_code == 302
    assert Notification.objects.filter(
        user=user,
        kind=Notification.Kind.STAFF_BROADCAST,
        title__startswith="Privé",
    ).exists()
    assert not Notification.objects.filter(
        user=other,
        kind=Notification.Kind.STAFF_BROADCAST,
        title__startswith="Privé",
    ).exists()
    from apps.dashboard.models import StaffBroadcast

    item = StaffBroadcast.objects.get(title="Privé")
    assert item.audience == StaffBroadcast.Audience.ONE
    assert item.recipient_id == user.pk
    assert item.recipient_count == 1


@pytest.mark.django_db
def test_staff_broadcast_one_requires_recipient(client, staff_user):
    client.force_login(staff_user)
    response = client.post(
        reverse("dashboard:staff_messaging") + "?tab=diffusions",
        {"title": "Sans cible", "body": "Oups", "audience": "one"},
    )
    assert response.status_code == 302
    from apps.dashboard.models import StaffBroadcast

    assert not StaffBroadcast.objects.filter(title="Sans cible").exists()
    assert not Notification.objects.filter(title__startswith="Sans cible").exists()


@pytest.mark.django_db
def test_staff_can_read_conversation(client, staff_user, listing, other):
    Conversation.objects.get_or_create_for(listing, listing.author, other)
    convo = Conversation.objects.get(listing=listing)
    Message.objects.create(conversation=convo, sender=other, body="Salut")
    client.force_login(staff_user)
    response = client.get(reverse("dashboard:conversation_detail", args=[convo.pk]))
    assert response.status_code == 200
    assert b"Salut" in response.content


@pytest.mark.django_db
def test_candidate_accept_required_before_contact(client, listing, other, city, profession):
    profile, _ = Profile.objects.get_or_create(user=other)
    profile.display_name = "Candidat"
    profile.city = city
    profile.primary_profession = profession
    profile.is_public = True
    profile.recommended_until = timezone.now() + timedelta(days=3)
    profile.recommend_score = 100
    profile.save()

    intro = CandidateIntroduction.objects.create(
        listing=listing,
        profile=profile,
        employer=listing.author,
        status=CandidateIntroduction.Status.PENDING,
    )
    client.force_login(listing.author)
    # Contact before accept should 404 (status filter)
    bad = client.post(reverse("recommendations:candidate_contact", args=[intro.pk]))
    assert bad.status_code == 404

    client.post(reverse("recommendations:candidate_decide", args=[intro.pk, "accept"]))
    intro.refresh_from_db()
    assert intro.status == CandidateIntroduction.Status.ACCEPTED

    ok = client.post(
        reverse("recommendations:candidate_contact", args=[intro.pk]),
        {"channel": "chat"},
    )
    assert ok.status_code == 302
    assert Conversation.objects.filter(listing=listing).exists()


@pytest.mark.django_db
def test_profile_boost_creates_staff_alert(staff_user, user, city, profession):
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.display_name = "Steevi"
    profile.city = city
    profile.primary_profession = profession
    profile.save()
    purchase = create_pending_purchase(
        user=user,
        kind=RecommendationPurchase.Kind.PROFILE,
        duration_days=1,
        profile=profile,
    )
    activate_purchase(purchase)
    assert Notification.objects.filter(
        user=staff_user,
        kind=Notification.Kind.STAFF_RECOMMENDATION,
    ).exists()
