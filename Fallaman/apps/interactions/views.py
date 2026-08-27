from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.ratelimit import rate_limit
from apps.listings.models import Listing
from apps.messaging.models import Conversation

from .services import InterestError, express_interest


@login_required
@require_http_methods(["GET", "POST"])
@rate_limit("interest", limit=30, window_seconds=3600)
def express(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    if request.method == "POST":
        try:
            express_interest(request.user, listing, request.POST.get("message", ""))
        except InterestError as exc:
            return render(
                request,
                "interactions/express.html",
                {"listing": listing, "error": str(exc)},
                status=400,
            )
        conversation = Conversation.objects.get_or_create_for(listing, request.user, listing.author)
        return redirect(conversation.get_absolute_url())
    return render(request, "interactions/express.html", {"listing": listing})
