import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.core.activity import log_activity
from apps.core.models import ActivityLog
from apps.core.tasks import cleanup_activity_logs

User = get_user_model()


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        phone_number="06119999", is_staff=True, phone_verified=True
    )


@pytest.mark.django_db
def test_log_activity_persists(user):
    entry = log_activity(
        action="test.ping",
        message="hello",
        category=ActivityLog.Category.SYSTEM,
        user=user,
    )
    assert entry is not None
    assert ActivityLog.objects.filter(action="test.ping").exists()


@pytest.mark.django_db
def test_activity_logs_dashboard(client, staff_user):
    log_activity(action="staff.view", message="probe", category=ActivityLog.Category.STAFF)
    client.force_login(staff_user)
    response = client.get(reverse("dashboard:activity_logs"))
    assert response.status_code == 200
    assert b"staff.view" in response.content


@pytest.mark.django_db
def test_activity_logs_htmx_partial(client, staff_user):
    log_activity(action="htmx.search", message="q", category=ActivityLog.Category.REQUEST)
    client.force_login(staff_user)
    response = client.get(
        reverse("dashboard:activity_logs"),
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert b"htmx.search" in response.content
    assert b"<h1>" not in response.content


@pytest.mark.django_db
def test_cleanup_activity_logs(settings):
    from datetime import timedelta

    from django.utils import timezone

    settings.ACTIVITY_LOG_RETENTION_DAYS = 7
    old = log_activity(action="old.one", message="old")
    fresh = log_activity(action="new.one", message="new")
    ActivityLog.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=30))
    cleanup_activity_logs()
    assert not ActivityLog.objects.filter(pk=old.pk).exists()
    assert ActivityLog.objects.filter(pk=fresh.pk).exists()
