from pathlib import Path

import pytest
from django.conf import settings
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
    assert b"icon-192.png" in response.content
    assert b"icon-512.png" in response.content
    assert b'"display": "standalone"' in response.content


def test_service_worker(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "javascript" in response["Content-Type"]
    assert response["Service-Worker-Allowed"] == "/"


@pytest.mark.django_db
def test_accueil_propose_linstallation_pwa(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"data-pwa-install" in response.content
    assert b"pwa-install-modal" in response.content
    assert b"Android" in response.content
    assert b"iOS" in response.content
    assert b"pwa-home-card" not in response.content
    assert b"data-app-store-pending" in response.content
    assert b"app-store-soon-modal" in response.content
    assert "Bient".encode("utf-8") in response.content or b"Bient\xc3\xb4t disponible" in response.content


@pytest.mark.django_db
def test_accueil_store_links_ouverts_si_url_reelle(client, settings):
    settings.ANDROID_APP_URL = "https://play.google.com/store/apps/details?id=ga.fallaman"
    settings.IOS_APP_URL = "https://apps.apple.com/app/fallaman/id000"
    response = client.get("/")
    assert response.status_code == 200
    assert b'data-app-store-pending="android"' not in response.content
    assert b'data-app-store-pending="ios"' not in response.content
    assert b"https://play.google.com/store/apps/details?id=ga.fallaman" in response.content
    assert b"https://apps.apple.com/app/fallaman/id000" in response.content


def test_icones_pwa_presentes():
    icons = Path(settings.BASE_DIR) / "static" / "icons"
    assert (icons / "icon-192.png").is_file()
    assert (icons / "icon-512.png").is_file()
