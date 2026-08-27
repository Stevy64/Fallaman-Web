from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("hors-ligne/", views.offline, name="offline"),
    path("a-propos/", views.page_about, name="about"),
    path("confidentialite/", views.page_privacy, name="privacy"),
    path("conditions/", views.page_terms, name="terms"),
    path("securite/", views.page_safety, name="safety"),
    path(
        "manifest.webmanifest",
        TemplateView.as_view(
            template_name="pwa/manifest.webmanifest",
            content_type="application/manifest+json",
        ),
        name="manifest",
    ),
]
