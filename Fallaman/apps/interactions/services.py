from django.db import transaction

from apps.listings.models import Listing
from apps.messaging.models import Conversation, Message
from apps.moderation.models import BlockedUser
from apps.notifications.services import notify

from .models import Interest


class InterestError(Exception):
    pass


def express_interest(user, listing: Listing, message: str = "") -> Interest:
    if listing.author_id == user.id:
        raise InterestError("Vous ne pouvez pas manifester d'intérêt pour votre propre annonce.")
    if not listing.is_published:
        raise InterestError("Cette annonce n'est plus disponible.")
    if BlockedUser.objects.is_blocked(user, listing.author):
        raise InterestError("Vous ne pouvez pas contacter cette personne.")

    with transaction.atomic():
        interest, created = Interest.objects.get_or_create(
            user=user, listing=listing, defaults={"message": message}
        )
        if not created:
            return interest
        conversation = Conversation.objects.get_or_create_for(listing, user, listing.author)
        if message.strip():
            Message.objects.create(conversation=conversation, sender=user, body=message.strip())
            conversation.touch()
        notify(
            listing.author,
            "new_interest",
            f"{user.display_name} est intéressé par « {listing.title} ».",
            url=conversation.get_absolute_url(),
        )
        return interest
