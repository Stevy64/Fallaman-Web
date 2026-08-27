from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.generic import TemplateView

from apps.accounts.forms import FallamanAdminAuthenticationForm
from apps.listings.sitemaps import ListingSitemap

admin.site.login_form = FallamanAdminAuthenticationForm
admin.site.site_header = "Fallaman"
admin.site.site_title = "Fallaman"
admin.site.index_title = "Administration"

sitemaps = {"listings": ListingSitemap}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.profiles.urls")),
    path("", include("apps.listings.urls")),
    path("", include("apps.interactions.urls")),
    path("", include("apps.taxonomy.urls")),
    path("", include("apps.messaging.urls")),
    path("", include("apps.notifications.urls")),
    path("", include("apps.moderation.urls")),
    path("tableau-de-bord/", include("apps.dashboard.urls")),
    path("", include("apps.payments.urls")),
    path("", include("apps.recommendations.urls")),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
    path(
        "sw.js",
        TemplateView.as_view(
            template_name="pwa/sw.js",
            content_type="application/javascript",
        ),
        name="service-worker",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
