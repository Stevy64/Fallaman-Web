from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.phone import contact_whatsapp_url
from apps.core.ratelimit import rate_limit
from apps.core.uploads import max_listing_images
from apps.core.utils import contains_suspicious_link, looks_like_money_request
from apps.interactions.models import Interest
from apps.locations.models import City, District, Province
from apps.moderation.models import Report
from apps.taxonomy.models import Profession

from .forms import (
    ListingDescriptionForm,
    ListingJobForm,
    ListingLocationForm,
    ListingTermsForm,
)
from .location_utils import resolve_location, resolve_profession
from .models import Favorite, Listing, ListingImage, SearchAlert
from .services import apply_filters, popular_searches, recent_listings, search_listings


def _draft(request):
    return request.session.setdefault("listing_draft", {})


def _location_suggestions():
    return {
        "provinces": Province.objects.order_by("sort_order", "name"),
        "cities": City.objects.order_by("name"),
        "districts": District.objects.select_related("city").order_by("name"),
        "professions": Profession.objects.filter(is_active=True).order_by("name"),
    }


@require_GET
def search(request):
    qs = recent_listings(ranked=False)
    query = request.GET.get("q", "").strip()
    qs = search_listings(qs, query)
    qs = apply_filters(qs, request.GET)
    paginator = Paginator(qs, 12)
    page = paginator.get_page(request.GET.get("page") or 1)
    context = {
        "listings": page,
        "query": query,
        # Toutes les villes : le champ est libre, mais la liste de suggestions
        # ne doit pas se limiter aux villes « populaires ».
        "cities": City.objects.order_by("name"),
        "provinces": Province.objects.order_by("sort_order", "name"),
        "duration_choices": Listing.Duration.choices,
        "availability_choices": Listing.Availability.choices,
        "page_obj": page,
        "popular_terms": popular_searches(),
    }
    if request.htmx:
        return render(request, "listings/partials/results.html", context)
    return render(request, "listings/search.html", context)


@require_GET
def listing_detail(request, slug, pk):
    listing = get_object_or_404(
        Listing.objects.select_related(
            "author", "author__profile", "city", "district", "profession", "province"
        ).prefetch_related("images"),
        pk=pk,
    )
    if listing.slug != slug:
        return redirect(listing.get_absolute_url(), permanent=True)
    if listing.status == Listing.Status.DELETED and listing.author != request.user:
        return render(request, "listings/unavailable.html", status=404)

    interested = False
    is_favorite = False
    if request.user.is_authenticated:
        interested = Interest.objects.filter(user=request.user, listing=listing).exists()
        is_favorite = Favorite.objects.filter(user=request.user, listing=listing).exists()

    whatsapp_text = (
        f"Bonjour, je vous contacte concernant votre annonce « {listing.title} » publiée sur Fallaman."
    )
    whatsapp_url = ""
    if listing.author_id != getattr(request.user, "id", None):
        whatsapp_url = contact_whatsapp_url(listing.author, text=whatsapp_text)

    recommended_candidates = []
    if request.user.is_authenticated and listing.author_id == request.user.id:
        from apps.recommendations.services import introductions_for_listing

        recommended_candidates = introductions_for_listing(listing)
        for intro in recommended_candidates:
            intro.whatsapp_url = ""
            if intro.can_contact:
                text = (
                    f"Bonjour, je vous contacte suite à votre recommandation sur Fallaman "
                    f"pour l'annonce « {listing.title} »."
                )
                intro.whatsapp_url = contact_whatsapp_url(intro.profile.user, text=text)

    return render(
        request,
        "listings/detail.html",
        {
            "listing": listing,
            "interested": interested,
            "is_favorite": is_favorite,
            "report_reasons": Report.Reason.choices,
            "whatsapp_url": whatsapp_url,
            "recommended_candidates": recommended_candidates,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def publish_start(request):
    listing_type = request.GET.get("type")
    if listing_type in {Listing.Type.EMPLOYMENT, Listing.Type.MISSION}:
        draft = _draft(request)
        draft["listing_type"] = listing_type
        request.session.modified = True
        return redirect("listings:publish_job")
    request.session["listing_draft"] = {}
    return render(request, "listings/publish_type.html")


@login_required
@require_http_methods(["GET", "POST"])
def publish_type(request):
    listing_type = request.POST.get("listing_type") or request.GET.get("type")
    if listing_type not in {Listing.Type.EMPLOYMENT, Listing.Type.MISSION}:
        messages.error(request, "Choisissez un type d'annonce.")
        return redirect("listings:publish")
    draft = _draft(request)
    draft["listing_type"] = listing_type
    request.session.modified = True
    return redirect("listings:publish_job")


@login_required
@require_http_methods(["GET", "POST"])
def publish_job(request):
    if "listing_type" not in request.session.get("listing_draft", {}):
        return redirect("listings:publish")
    draft = request.session.get("listing_draft", {})
    initial = {"job": draft.get("job_label") or draft.get("custom_profession") or ""}
    if not initial["job"] and draft.get("profession_id"):
        profession = Profession.objects.filter(pk=draft["profession_id"]).first()
        if profession:
            initial["job"] = profession.name
    form = ListingJobForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        profession, custom = resolve_profession(form.cleaned_data["job"])
        draft = _draft(request)
        draft["profession_id"] = profession.pk if profession else None
        draft["custom_profession"] = custom
        draft["job_label"] = form.cleaned_data["job"]
        request.session.modified = True
        return redirect("listings:publish_location")
    context = {
        "form": form,
        "step": 1,
        "back_url": reverse("listings:publish"),
        **_location_suggestions(),
    }
    return render(request, "listings/publish_job.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def publish_location(request):
    if "listing_type" not in request.session.get("listing_draft", {}):
        return redirect("listings:publish")
    draft = request.session.get("listing_draft", {})
    initial = {
        "province": draft.get("province_name") or "",
        "city": draft.get("city_name") or "",
        "district": draft.get("district_name") or "",
    }
    if not initial["province"] and draft.get("province_id"):
        province = Province.objects.filter(pk=draft["province_id"]).first()
        if province:
            initial["province"] = province.name
    if not initial["city"] and draft.get("city_id"):
        city = City.objects.filter(pk=draft["city_id"]).first()
        if city:
            initial["city"] = city.name
    if not initial["district"] and draft.get("district_id"):
        district = District.objects.filter(pk=draft["district_id"]).first()
        if district:
            initial["district"] = district.name
    form = ListingLocationForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            province, city, district = resolve_location(
                form.cleaned_data["province"],
                form.cleaned_data["city"],
                form.cleaned_data["district"],
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            draft = _draft(request)
            draft["province_id"] = province.pk
            draft["city_id"] = city.pk
            draft["district_id"] = district.pk if district else None
            draft["province_name"] = province.name
            draft["city_name"] = city.name
            draft["district_name"] = district.name if district else ""
            request.session.modified = True
            return redirect("listings:publish_terms")
    context = {
        "form": form,
        "step": 2,
        "back_url": reverse("listings:publish_job"),
        **_location_suggestions(),
    }
    return render(request, "listings/publish_location.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def publish_terms(request):
    if "listing_type" not in request.session.get("listing_draft", {}):
        return redirect("listings:publish")
    draft = request.session.get("listing_draft", {})
    initial = {
        "duration": draft.get("duration") or "",
        "salary_type": draft.get("salary_type") or "",
        "salary_amount": draft.get("salary_amount"),
        "availability": draft.get("availability") or "",
        "work_date": draft.get("work_date") or None,
    }
    form = ListingTermsForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        draft = _draft(request)
        draft.update(
            {
                "duration": form.cleaned_data["duration"],
                "salary_type": form.cleaned_data["salary_type"],
                "salary_amount": form.cleaned_data["salary_amount"],
                "availability": form.cleaned_data["availability"],
                "work_date": form.cleaned_data["work_date"].isoformat()
                if form.cleaned_data["work_date"]
                else None,
            }
        )
        request.session.modified = True
        return redirect("listings:publish_description")
    return render(
        request,
        "listings/publish_terms.html",
        {
            "form": form,
            "step": 3,
            "back_url": reverse("listings:publish_location"),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
@rate_limit("publish", limit=10, window_seconds=3600)
def publish_description(request):
    draft = request.session.get("listing_draft") or {}
    if "listing_type" not in draft:
        return redirect("listings:publish")
    if request.method == "POST":
        form = ListingDescriptionForm(request.POST, request.FILES)
    else:
        form = ListingDescriptionForm(initial={"description": draft.get("description") or ""})
    if request.method == "POST" and form.is_valid():
        draft = request.session.get("listing_draft") or {}
        if "listing_type" not in draft:
            return redirect("listings:publish")
        with transaction.atomic():
            listing = Listing(
                author=request.user,
                listing_type=draft["listing_type"],
                profession_id=draft.get("profession_id"),
                custom_profession=draft.get("custom_profession") or "",
                description=form.cleaned_data["description"],
                province_id=draft.get("province_id"),
                city_id=draft.get("city_id"),
                district_id=draft.get("district_id"),
                salary_type=draft.get("salary_type") or Listing.SalaryType.NEGOTIABLE,
                salary_amount=draft.get("salary_amount"),
                duration=draft.get("duration") or "",
                availability=draft.get("availability") or "",
            )
            if draft.get("work_date"):
                from datetime import date

                listing.work_date = date.fromisoformat(draft["work_date"])
            if looks_like_money_request(listing.description) or contains_suspicious_link(listing.description):
                listing.status = Listing.Status.PENDING
            listing.save()
            # On repart des fichiers *validés* par le formulaire, pas de
            # request.FILES brut, sinon le contrôle de taille et de format saute.
            files = form.cleaned_data.get("images") or []
            for index, uploaded in enumerate(files[:max_listing_images()]):
                ListingImage.objects.create(listing=listing, image=uploaded, sort_order=index)
            if listing.status != Listing.Status.PENDING:
                listing.publish()
            else:
                listing.save()
        request.session.pop("listing_draft", None)
        if listing.status == Listing.Status.PENDING:
            messages.warning(request, "Votre annonce est en cours de vérification.")
        else:
            messages.success(request, "Votre annonce est en ligne.")
        return redirect(listing.get_absolute_url())
    return render(
        request,
        "listings/publish_description.html",
        {
            "form": form,
            "step": 4,
            "back_url": reverse("listings:publish_terms"),
        },
    )


@login_required
@require_POST
def listing_renew(request, pk):
    listing = get_object_or_404(Listing, pk=pk, author=request.user)
    listing.renew()
    messages.success(request, "Annonce renouvelée.")
    return redirect(listing.get_absolute_url())


@login_required
@require_POST
def listing_filled(request, pk):
    listing = get_object_or_404(Listing, pk=pk, author=request.user)
    listing.mark_filled()
    messages.success(request, "Annonce marquée comme pourvue.")
    return redirect("profiles:mine")


@login_required
@require_POST
def listing_delete(request, pk):
    listing = get_object_or_404(Listing, pk=pk, author=request.user)
    listing.status = Listing.Status.DELETED
    listing.save(update_fields=["status", "updated_at"])
    messages.info(request, "Annonce retirée.")
    return redirect("profiles:mine")


@login_required
@require_GET
def listing_duplicate(request, pk):
    listing = get_object_or_404(Listing, pk=pk, author=request.user)
    request.session["listing_draft"] = {
        "listing_type": listing.listing_type,
        "profession_id": listing.profession_id,
        "custom_profession": listing.custom_profession,
        "province_id": listing.province_id,
        "city_id": listing.city_id,
        "district_id": listing.district_id,
        "salary_type": listing.salary_type,
        "salary_amount": listing.salary_amount,
        "duration": listing.duration,
        "availability": listing.availability,
    }
    messages.info(request, "Annonce dupliquée. Vérifiez les informations puis publiez.")
    return redirect("listings:publish_job")


@login_required
@require_POST
def toggle_favorite(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    favorite, created = Favorite.objects.get_or_create(user=request.user, listing=listing)
    if not created:
        favorite.delete()
        saved = False
    else:
        saved = True
    if request.htmx:
        return render(
            request,
            "listings/partials/favorite_button.html",
            {"listing": listing, "is_favorite": saved},
        )
    return redirect(listing.get_absolute_url())


@login_required
@require_GET
def favorites(request):
    items = (
        Favorite.objects.filter(user=request.user)
        .select_related("listing", "listing__city", "listing__profession")
        .order_by("-created_at")
    )
    return render(request, "listings/favorites.html", {"favorites": items})


@login_required
@require_POST
def create_alert(request):
    query = (request.POST.get("q") or "").strip()
    raw_city = (request.POST.get("city") or "").strip()
    city_id = int(raw_city) if raw_city.isdigit() else None
    listing_type = request.POST.get("type") or ""
    if not query and not city_id and not listing_type:
        messages.info(request, "Indiquez un métier ou un filtre pour créer une alerte.")
        return redirect("listings:search")
    _, created = SearchAlert.objects.get_or_create(
        user=request.user,
        query=query,
        city_id=city_id,
        listing_type=listing_type,
        defaults={"is_active": True},
    )
    if created:
        messages.success(request, "Alerte créée. Nous vous préviendrons dès qu'un poste correspond à votre recherche.")
    else:
        messages.info(request, "Cette alerte existe déjà.")
    return redirect("listings:search")
