from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

from apps.core.utils import normalize_text
from apps.taxonomy.models import Profession, ProfessionAlias

from .models import Listing


POPULAR_SEARCHES = [
    "Nounou",
    "Chauffeur",
    "Ménagère",
    "Maçon",
    "Gardien",
    "Débroussailleur",
    "Serveur",
]


def popular_searches():
    return POPULAR_SEARCHES


def recent_listings(*, ranked: bool = True):
    from apps.recommendations.services import with_boost_ranking

    qs = (
        Listing.objects.published()
        .select_related("city", "district", "profession", "author", "author__profile")
        .prefetch_related("images")
    )
    if ranked:
        return with_boost_ranking(qs)
    return qs


def matching_profession_ids(query: str) -> list[int]:
    needle = normalize_text(query)
    if not needle:
        return []
    profession_ids = list(
        Profession.objects.filter(
            Q(normalized_name__icontains=needle) | Q(name__icontains=query)
        ).values_list("id", flat=True)
    )
    alias_ids = list(
        ProfessionAlias.objects.filter(
            Q(normalized_name__icontains=needle) | Q(name__icontains=query)
        ).values_list("profession_id", flat=True)
    )
    return list({*profession_ids, *alias_ids})


def search_listings(queryset, query: str):
    query = (query or "").strip()
    if not query:
        return queryset
    ids = matching_profession_ids(query)
    filters = (
        Q(title__icontains=query)
        | Q(description__icontains=query)
        | Q(custom_profession__icontains=query)
    )
    if ids:
        filters |= Q(profession_id__in=ids)
    return queryset.filter(filters)


def apply_filters(queryset, params):
    listing_type = params.get("type")
    if listing_type in {Listing.Type.EMPLOYMENT, Listing.Type.MISSION}:
        queryset = queryset.filter(listing_type=listing_type)
    city = params.get("city")
    city_name = (params.get("city_name") or "").strip()
    if city:
        queryset = queryset.filter(city_id=city)
    elif city_name:
        queryset = queryset.filter(city__name__icontains=city_name)
    province = params.get("province")
    if province:
        queryset = queryset.filter(province_id=province)
    duration = params.get("duration")
    if duration:
        queryset = queryset.filter(duration=duration)
    availability = params.get("availability")
    if availability:
        queryset = queryset.filter(availability=availability)
    profession = params.get("profession")
    if profession:
        queryset = queryset.filter(profession_id=profession)
    category = params.get("category")
    if category:
        queryset = queryset.filter(profession__category_id=category)
    salary_min = params.get("salary_min")
    if salary_min:
        try:
            queryset = queryset.filter(salary_amount__gte=int(salary_min))
        except ValueError:
            pass
    sort = params.get("sort", "recent")
    from apps.recommendations.services import with_boost_ranking

    return with_boost_ranking(queryset, sort=sort)


def _preferred_listing_type(looking_for: str):
    text = (looking_for or "").lower()
    if "mission" in text:
        return Listing.Type.MISSION
    if "emploi" in text or "travail" in text:
        return Listing.Type.EMPLOYMENT
    return None


def recommend_for_profile(profile, limit=8):
    """Recommandations simples : métier, ville, texte « je recherche »."""
    base = recent_listings()
    if not profile:
        return list(base[:limit])

    base = base.exclude(author_id=profile.user_id)
    has_signal = bool(
        profile.primary_profession_id or profile.city_id or (profile.looking_for or "").strip()
    )
    if not has_signal:
        return list(base[:limit])

    preferred_type = _preferred_listing_type(profile.looking_for)
    qs = base
    if preferred_type:
        typed = qs.filter(listing_type=preferred_type)
        if typed.exists():
            qs = typed

    relevance = Q(pk__in=[])
    if profile.primary_profession_id:
        relevance |= Q(profession_id=profile.primary_profession_id)
        category_id = getattr(getattr(profile, "primary_profession", None), "category_id", None)
        if category_id:
            relevance |= Q(profession__category_id=category_id)

    looking = (profile.looking_for or "").strip()
    if looking:
        ids = matching_profession_ids(looking)
        relevance |= (
            Q(title__icontains=looking)
            | Q(description__icontains=looking)
            | Q(custom_profession__icontains=looking)
        )
        if ids:
            relevance |= Q(profession_id__in=ids)

    if profile.city_id:
        relevance |= Q(city_id=profile.city_id)

    matched = qs.filter(relevance)
    if not matched.exists():
        return list(qs[:limit])

    ranked = matched.annotate(
        match_rank=Case(
            When(profession_id=profile.primary_profession_id, then=Value(0)),
            When(city_id=profile.city_id, then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        ),
        boost_active=Case(
            When(boosted_until__gt=timezone.now(), then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
    ).order_by("match_rank", "-boost_active", "-boost_score", "-published_at")
    return list(ranked[:limit])


SEARCH_STOPWORDS = {
    "emploi",
    "mission",
    "travail",
    "boulot",
    "poste",
    "recherche",
    "recherches",
    "je",
    "un",
    "une",
    "des",
    "le",
    "la",
    "les",
    "du",
    "de",
    "ou",
    "et",
    "mon",
    "ma",
    "mes",
    "pour",
    "avec",
    "dans",
    "sur",
    "au",
    "en",
}


def search_intent_tokens(text: str) -> list[str]:
    import re

    raw = (text or "").strip()
    if not raw:
        return []
    parts = re.split(r"[,/;:·|\n]|\s+ou\s+|\s+et\s+", raw, flags=re.I)
    tokens = []
    seen = set()
    for part in parts:
        cleaned = re.sub(r"\s+", " ", part).strip()
        key = normalize_text(cleaned)
        if len(key) < 3 or key in SEARCH_STOPWORDS or key in seen:
            continue
        seen.add(key)
        tokens.append(cleaned)
    return tokens


def listing_search_terms(listing) -> list[str]:
    terms = []
    seen = set()

    def add(value: str):
        text = (value or "").strip()
        key = normalize_text(text)
        if len(key) < 3 or key in SEARCH_STOPWORDS or key in seen:
            return
        seen.add(key)
        terms.append(text)

    add(listing.custom_profession)
    if listing.profession_id:
        add(listing.profession.name)
        for alias in listing.profession.aliases.all():
            add(alias.name)
    add(listing.job_label)
    return terms


def listing_matches_search_intent(listing, intent: str) -> bool:
    intent = (intent or "").strip()
    if not intent:
        return False
    qs = Listing.objects.filter(pk=listing.pk)
    if search_listings(qs, intent).exists():
        return True
    for token in search_intent_tokens(intent):
        if search_listings(qs, token).exists():
            return True
    return False


def alert_matches_listing(alert, listing) -> bool:
    if alert.listing_type and alert.listing_type != listing.listing_type:
        return False
    if alert.city_id and alert.city_id != listing.city_id:
        return False
    if alert.profession_id and listing.profession_id and alert.profession_id != listing.profession_id:
        return False
    if alert.query:
        return listing_matches_search_intent(listing, alert.query)
    return bool(alert.profession_id or alert.city_id)


def profiles_matching_listing(listing, limit=40):
    """Profils dont la recherche / le métier correspond à l'annonce."""
    from apps.profiles.models import Profile

    qs = Profile.objects.exclude(user_id=listing.author_id).select_related(
        "user", "primary_profession"
    )
    relevance = Q()
    if listing.profession_id:
        relevance |= Q(primary_profession_id=listing.profession_id)

    for term in listing_search_terms(listing):
        relevance |= Q(looking_for__icontains=term)
        for token in search_intent_tokens(term):
            relevance |= Q(looking_for__icontains=token)

    if not relevance:
        return []

    candidates = list(qs.filter(relevance).distinct()[: max(limit * 3, 40)])
    matched = []
    for profile in candidates:
        looking = (profile.looking_for or "").strip()
        profession_hit = bool(
            profile.primary_profession_id
            and listing.profession_id
            and profile.primary_profession_id == listing.profession_id
        )
        search_hit = listing_matches_search_intent(listing, looking) if looking else False
        if profession_hit or search_hit:
            matched.append(profile)
        if len(matched) >= limit:
            break
    return matched


def users_to_notify_for_listing(listing, limit=40):
    """Utilisateurs à prévenir : profil (recherche/métier) + alertes de recherche."""
    from apps.listings.models import SearchAlert

    seen = set()
    recipients = []

    def add(user, alert=None):
        if not user or user.pk == listing.author_id or user.pk in seen:
            return
        seen.add(user.pk)
        recipients.append((user, alert))

    for profile in profiles_matching_listing(listing, limit=limit):
        add(profile.user)

    alerts = (
        SearchAlert.objects.filter(is_active=True)
        .exclude(user_id=listing.author_id)
        .select_related("user", "profession", "city")
    )
    for alert in alerts:
        if alert_matches_listing(alert, listing):
            add(alert.user, alert)
        if len(recipients) >= limit:
            break
    return recipients[:limit]
