from celery import shared_task
from django.utils import timezone

from .models import Conversation, Message


@shared_task
def expire_conversations():
    now = timezone.now()
    expired = Conversation.objects.filter(is_expired=False).filter(
        models_q_expires(now)
    )
    count = 0
    for conversation in expired:
        conversation.messages.all().delete()
        conversation.is_expired = True
        conversation.save(update_fields=["is_expired"])
        count += 1
    Message.objects.filter(conversation__is_expired=True).delete()
    return count


def models_q_expires(now):
    from django.db.models import Q

    return Q(expires_at__lte=now) | Q(hard_expires_at__lte=now)
