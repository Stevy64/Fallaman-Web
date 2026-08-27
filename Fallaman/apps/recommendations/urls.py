from django.urls import path

from . import views

app_name = "recommendations"

urlpatterns = [
    path(
        "annonces/<int:pk>/recommander/",
        views.boost_listing,
        name="boost_listing",
    ),
    path(
        "profil/etre-recommande/",
        views.boost_profile,
        name="boost_profile",
    ),
    path(
        "mes-recommandations/",
        views.my_recommendations,
        name="mine",
    ),
    path(
        "mises-en-relation/<int:pk>/contacter/",
        views.candidate_contact,
        name="candidate_contact",
    ),
    path(
        "mises-en-relation/<int:pk>/<str:action>/",
        views.candidate_decide,
        name="candidate_decide",
    ),
]
