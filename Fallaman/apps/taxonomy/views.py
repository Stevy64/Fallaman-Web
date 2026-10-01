from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, render

from apps.listings.models import Listing

from .models import Category, Profession


def category_list(request):
    active_professions = Prefetch(
        "professions",
        queryset=Profession.objects.filter(is_active=True).order_by("sort_order", "name"),
    )
    categories = (
        Category.objects.filter(is_active=True)
        .annotate(
            profession_count=Count(
                "professions",
                filter=Q(professions__is_active=True),
                distinct=True,
            )
        )
        .prefetch_related(active_professions)
        .order_by("sort_order", "name")
    )
    return render(
        request,
        "taxonomy/categories.html",
        {
            "categories": categories,
            "category_count": categories.count(),
        },
    )


def category_detail(request, slug):
    category = get_object_or_404(
        Category.objects.annotate(
            profession_count=Count(
                "professions",
                filter=Q(professions__is_active=True),
                distinct=True,
            )
        ),
        slug=slug,
        is_active=True,
    )
    professions = category.professions.filter(is_active=True)
    listings = (
        Listing.objects.published()
        .filter(profession__category=category)
        .select_related("city", "district", "profession", "author", "author__profile")
        .order_by("-published_at")[:50]
    )
    return render(
        request,
        "taxonomy/category_detail.html",
        {
            "category": category,
            "professions": professions,
            "listings": listings,
            "listing_count": len(listings),
        },
    )
