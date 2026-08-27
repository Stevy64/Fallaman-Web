from datetime import timedelta

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from .models import Notification

UNREAD_TTL_HOURS = 24
READ_TTL_DAYS = 3


@shared_task
def cleanup_notifications():
    """Supprime les non lues > 24 h et les lues > 3 jours (hors messages équipe)."""
    now = timezone.now()
    unread_before = now - timedelta(hours=UNREAD_TTL_HOURS)
    read_before = now - timedelta(days=READ_TTL_DAYS)
    classic = ~Q(kind=Notification.Kind.STAFF_BROADCAST)

    deleted_unread, _ = Notification.objects.filter(
        classic,
        is_read=False,
        created_at__lt=unread_before,
    ).delete()

    deleted_read, _ = Notification.objects.filter(classic, is_read=True).filter(
        Q(read_at__lt=read_before) | Q(read_at__isnull=True, created_at__lt=read_before)
    ).delete()

    return deleted_unread + deleted_read
