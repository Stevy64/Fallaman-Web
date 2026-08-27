from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import broadcast_notification, notify
from apps.notifications.tasks import cleanup_notifications


@pytest.mark.django_db
def test_classic_notification_deleted_on_open(client, user):
    item = notify(user, Notification.Kind.SYSTEM, "Ping", url="/")
    client.force_login(user)
    response = client.get(reverse("notifications:open", args=[item.pk]))
    assert response.status_code == 302
    assert not Notification.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db
def test_staff_broadcast_opens_without_delete(client, user):
    broadcast_notification(title="Info équipe", body="Détail important", audience="active")
    item = Notification.objects.get(user=user, kind=Notification.Kind.STAFF_BROADCAST)
    client.force_login(user)

    page = client.get(reverse("notifications:open", args=[item.pk]))
    assert page.status_code == 200
    assert "Détail important".encode() in page.content
    item.refresh_from_db()
    assert item.is_read is True
    assert Notification.objects.filter(pk=item.pk).exists()

    api = client.get(
        reverse("notifications:open", args=[item.pk]),
        HTTP_ACCEPT="application/json",
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert api.status_code == 200
    data = api.json()
    assert data["title"] == "Info équipe"
    assert data["body"] == "Détail important"
    assert data["persistent"] is True
    assert Notification.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db
def test_staff_broadcast_deleted_only_explicitly(client, user):
    broadcast_notification(title="À garder", body="Corps", audience="active")
    item = Notification.objects.get(user=user, kind=Notification.Kind.STAFF_BROADCAST)
    client.force_login(user)
    client.get(reverse("notifications:open", args=[item.pk]))
    assert Notification.objects.filter(pk=item.pk).exists()

    deleted = client.post(reverse("notifications:delete", args=[item.pk]))
    assert deleted.status_code == 302
    assert not Notification.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db
def test_cleanup_skips_staff_broadcast(user):
    old = timezone.now() - timedelta(days=10)
    classic = notify(user, Notification.Kind.SYSTEM, "Ancien")
    Notification.objects.filter(pk=classic.pk).update(is_read=True, read_at=old, created_at=old)
    broadcast_notification(title="Persistant", body="Reste", audience="active")
    staff = Notification.objects.get(user=user, kind=Notification.Kind.STAFF_BROADCAST)
    Notification.objects.filter(pk=staff.pk).update(is_read=True, read_at=old, created_at=old)

    cleanup_notifications()
    assert not Notification.objects.filter(pk=classic.pk).exists()
    assert Notification.objects.filter(pk=staff.pk).exists()
