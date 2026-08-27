from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import ActivityLog


@shared_task
def cleanup_activity_logs():
    days = getattr(settings, "ACTIVITY_LOG_RETENTION_DAYS", 30)
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = ActivityLog.objects.filter(created_at__lt=cutoff).delete()
    return deleted
