from django import template

from apps.core.utils import format_fcfa, relative_date

register = template.Library()

CATEGORY_ICON_MAP = {
    "home": "bi-house-heart-fill",
    "truck": "bi-truck",
    "bricks": "bi-bricks",
    "leaf": "bi-tree-fill",
    "utensils": "bi-cup-hot-fill",
    "shop": "bi-shop",
    "sparkle": "bi-stars",
    "wrench": "bi-wrench-adjustable",
    "laptop": "bi-laptop",
    "building": "bi-building",
    "box": "bi-box-seam-fill",
    "shield": "bi-shield-check",
    "book": "bi-book-half",
}


@register.filter
def fcfa(value):
    return format_fcfa(value)


@register.filter
def relative(value):
    return relative_date(value)


@register.filter
def listing_duration(listing):
    return listing.get_duration_display() if listing.duration else ""


@register.filter
def category_icon(value):
    """Mappe la clé d'icône stockée en base vers une classe Bootstrap Icons."""
    if not value:
        return "bi-grid-fill"
    key = str(value).strip().lower()
    if key.startswith("bi-"):
        return key
    return CATEGORY_ICON_MAP.get(key, "bi-grid-fill")


@register.inclusion_tag("components/hidden_filters.html", takes_context=True)
def hidden_filters(context, exclude=""):
    """
    Rejoue les filtres actifs en champs cachés.

    La page de recherche porte trois formulaires distincts (texte, tri,
    panneau de filtres). Sans ce report, chacun repart des seuls champs qu'il
    affiche et efface silencieusement les choix faits dans les deux autres.
    ``exclude`` liste les paramètres que le formulaire appelant gère lui-même.
    """
    from apps.listings.services import FILTER_PARAMS

    request = context.get("request")
    if request is None:
        return {"params": []}

    ignores = {part.strip() for part in exclude.split(",") if part.strip()}
    ignores.add("page")  # tout changement de filtre ramène à la première page

    params = []
    for key in FILTER_PARAMS:
        if key in ignores:
            continue
        value = (request.GET.get(key) or "").strip()
        if value:
            params.append((key, value))
    return {"params": params}


@register.simple_tag(takes_context=True)
def active_filter_count(context):
    """Nombre de filtres actifs, hors recherche texte et tri."""
    from apps.listings.services import FILTER_PARAMS

    request = context.get("request")
    if request is None:
        return 0
    ignores = {"q", "sort", "page"}
    return sum(
        1
        for key in FILTER_PARAMS
        if key not in ignores and (request.GET.get(key) or "").strip()
    )
