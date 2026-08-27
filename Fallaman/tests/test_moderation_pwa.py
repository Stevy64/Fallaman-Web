from django.urls import reverse

from apps.moderation.models import Report


def test_anonymous_cannot_report(client, listing):
    response = client.get(reverse("moderation:report", args=[listing.pk]))
    assert response.status_code == 302


def test_user_can_report(client, listing, other):
    client.force_login(other)
    response = client.post(
        reverse("moderation:report", args=[listing.pk]),
        {"reason": Report.Reason.SCAM, "details": "Demande d'argent"},
    )
    assert response.status_code == 302
    assert Report.objects.filter(listing=listing, reporter=other).exists()


def test_health(client):
    response = client.get("/health/")
    assert response.json()["status"] == "ok"


def test_manifest(client):
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert b"Fallaman" in response.content


def test_service_worker(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
