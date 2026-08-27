from django.contrib.sitemaps import Sitemap

from .models import Listing


class ListingSitemap(Sitemap):
    changefreq = "hourly"
    priority = 0.8

    def items(self):
        return Listing.objects.published().select_related("city")

    def lastmod(self, obj):
        return obj.updated_at
