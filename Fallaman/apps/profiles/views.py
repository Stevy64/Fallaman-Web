from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.listings.models import Listing

from apps.locations.models import City, District, Province
from apps.taxonomy.models import Profession

from .forms import ProfileForm
from .models import Profile


@login_required
@require_http_methods(["GET", "POST"])
def my_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("profiles:mine")
    else:
        form = ProfileForm(instance=profile)
    listings = Listing.objects.filter(author=request.user).exclude(status=Listing.Status.DELETED)
    return render(
        request,
        "profiles/mine.html",
        {
            "form": form,
            "profile": profile,
            "listings": listings,
            "provinces": Province.objects.order_by("sort_order", "name"),
            "cities": City.objects.order_by("name"),
            "districts": District.objects.select_related("city").order_by("name"),
            "professions": Profession.objects.filter(is_active=True).order_by("name"),
        },
    )


def public_profile(request, pk):
    profile = get_object_or_404(Profile, pk=pk, is_public=True)
    listings = Listing.objects.published().filter(author=profile.user)[:12]
    return render(request, "profiles/public.html", {"profile": profile, "listings": listings})
