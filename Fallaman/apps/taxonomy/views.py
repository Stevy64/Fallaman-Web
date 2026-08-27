from django.shortcuts import get_object_or_404, render

from apps.listings.models import Listing

from .models import Category


def category_list(request):
    categories = Category.objects.filter(is_active=True).prefetch_related("professions")
    return render(request, "taxonomy/categories.html", {"categories": categories})


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    listings = (
        Listing.objects.published()
        .filter(profession__category=category)
        .select_related("city", "district", "profession", "author")[:50]
    )
    return render(
        request,
        "taxonomy/category_detail.html",
        {"category": category, "listings": listings},
    )
