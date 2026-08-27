from django import template

from apps.core.utils import format_fcfa, relative_date

register = template.Library()


@register.filter
def fcfa(value):
    return format_fcfa(value)


@register.filter
def relative(value):
    return relative_date(value)


@register.filter
def listing_duration(listing):
    return listing.get_duration_display() if listing.duration else ""
