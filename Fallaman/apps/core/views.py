from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def home(request):
    from apps.listings.models import Listing
    from apps.listings.services import popular_searches, recent_listings, recommend_for_profile
    from apps.taxonomy.models import Category

    recommended = False
    listings = list(recent_listings()[:8])
    if request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        if profile and (
            profile.primary_profession_id or profile.city_id or (profile.looking_for or "").strip()
        ):
            matched = recommend_for_profile(profile, limit=8)
            if matched:
                listings = matched
                recommended = True

    categories = Category.objects.filter(is_active=True).order_by("sort_order", "name")
    return render(
        request,
        "pages/home.html",
        {
            "listings": listings,
            "recommended": recommended,
            "categories": categories,
            "popular_searches": popular_searches(),
            "listing_count": Listing.objects.published().count(),
        },
    )


@require_GET
def health(_request):
    return JsonResponse({"status": "ok", "service": "fallaman"})


@require_GET
def offline(request):
    return render(request, "pwa/offline.html")


@require_GET
def page_about(request):
    return render(request, "pages/about.html")


@require_GET
def page_privacy(request):
    return render(request, "pages/privacy.html")


@require_GET
def page_terms(request):
    return render(request, "pages/terms.html")


@require_GET
def page_safety(request):
    return render(request, "pages/safety.html")
