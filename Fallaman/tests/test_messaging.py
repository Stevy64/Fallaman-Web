from apps.interactions.services import InterestError, express_interest
from apps.messaging.models import Conversation, Message
from apps.messaging.tasks import expire_conversations
from django.utils import timezone
from datetime import timedelta


def test_interest_creates_conversation(listing, other):
    express_interest(other, listing, "Bonjour, je suis disponible.")
    conversation = Conversation.objects.get(listing=listing)
    assert conversation.has_member(other)
    assert conversation.has_member(listing.author)
    assert Message.objects.filter(conversation=conversation).count() == 1


def test_cannot_interest_own_listing(listing):
    try:
        express_interest(listing.author, listing)
        assert False
    except InterestError:
        pass


def test_blocked_user_cannot_interest(listing, other):
    from apps.moderation.models import BlockedUser

    BlockedUser.objects.create(blocker=listing.author, blocked=other)
    try:
        express_interest(other, listing)
        assert False
    except InterestError:
        pass


def test_conversation_expiry_deletes_messages(listing, other):
    express_interest(other, listing, "Disponible demain")
    conversation = Conversation.objects.get(listing=listing)
    conversation.expires_at = timezone.now() - timedelta(minutes=1)
    conversation.hard_expires_at = timezone.now() - timedelta(minutes=1)
    conversation.save()
    expire_conversations()
    conversation.refresh_from_db()
    assert conversation.is_expired
    assert conversation.messages.count() == 0
