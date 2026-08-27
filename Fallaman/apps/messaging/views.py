from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.accounts.phone import contact_whatsapp_url
from apps.core.ratelimit import rate_limit
from apps.moderation.models import BlockedUser
from apps.notifications.services import notify

from .models import Conversation, Message
from .tasks import expire_conversations


@login_required
def inbox(request):
    expire_conversations()
    conversations = (
        Conversation.objects.visible_for(request.user)
        .select_related("listing", "user_low", "user_high", "listing__city")
        .prefetch_related("messages")
    )
    items = []
    for conversation in conversations:
        conversation.counterpart = conversation.other_user(request.user)
        items.append(conversation)
    return render(request, "messaging/inbox.html", {"conversations": items})


@login_required
@require_http_methods(["GET", "POST"])
@rate_limit("messages", limit=60, window_seconds=3600)
def thread(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk)
    if not conversation.has_member(request.user):
        return render(request, "messaging/forbidden.html", status=403)

    other = conversation.other_user(request.user)
    if conversation.is_expired or timezone.now() >= conversation.effective_expiry:
        conversation.messages.all().delete()
        conversation.is_expired = True
        conversation.save(update_fields=["is_expired"])
        return render(
            request,
            "messaging/thread.html",
            {
                "conversation": conversation,
                "other": other,
                "expired": True,
                "chat_messages": [],
            },
        )

    if request.method == "POST":
        body = (request.POST.get("body") or "").strip()
        if body and not BlockedUser.objects.is_blocked(request.user, other):
            Message.objects.create(conversation=conversation, sender=request.user, body=body[:2000])
            conversation.touch()
            notify(
                other,
                "new_message",
                f"{request.user.display_name} vous a écrit.",
                url=conversation.get_absolute_url(),
            )
            return redirect(conversation.get_absolute_url())

    conversation.messages.exclude(sender=request.user).update(is_read=True)
    chat_messages = conversation.messages.select_related("sender")
    i_blocked = BlockedUser.objects.filter(blocker=request.user, blocked=other).exists()
    blocked_either = BlockedUser.objects.is_blocked(request.user, other)
    whatsapp_url = ""
    if not blocked_either:
        text = (
            f"Bonjour, je vous contacte concernant votre annonce « {conversation.listing.title} » "
            "publiée sur Fallaman."
        )
        whatsapp_url = contact_whatsapp_url(other, text=text)

    remaining = conversation.remaining
    total_minutes = max(0, int(remaining.total_seconds() // 60))
    days = total_minutes // (24 * 60)
    hours = (total_minutes % (24 * 60)) // 60
    minutes = total_minutes % 60
    if days > 0:
        remaining_label = f"{days} j {hours} h"
    elif hours > 0:
        remaining_label = f"{hours} h {minutes} min"
    else:
        remaining_label = f"{minutes} min"

    return render(
        request,
        "messaging/thread.html",
        {
            "conversation": conversation,
            "other": other,
            "chat_messages": chat_messages,
            "expired": False,
            "whatsapp_url": whatsapp_url,
            "remaining_label": remaining_label,
            "i_blocked": i_blocked,
            "blocked_either": blocked_either,
        },
    )
