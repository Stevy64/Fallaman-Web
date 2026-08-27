from django.urls import path

from . import views

app_name = "listings"

urlpatterns = [
    path("rechercher/", views.search, name="search"),
    path("annonces/<slug:slug>-<int:pk>/", views.listing_detail, name="detail"),
    path("publier/", views.publish_start, name="publish"),
    path("publier/type/", views.publish_type, name="publish_type"),
    path("publier/metier/", views.publish_job, name="publish_job"),
    path("publier/lieu/", views.publish_location, name="publish_location"),
    path("publier/conditions/", views.publish_terms, name="publish_terms"),
    path("publier/details/", views.publish_description, name="publish_description"),
    path("annonces/<int:pk>/renouveler/", views.listing_renew, name="renew"),
    path("annonces/<int:pk>/pourvu/", views.listing_filled, name="filled"),
    path("annonces/<int:pk>/supprimer/", views.listing_delete, name="delete"),
    path("annonces/<int:pk>/dupliquer/", views.listing_duplicate, name="duplicate"),
    path("annonces/<int:pk>/favori/", views.toggle_favorite, name="favorite"),
    path("favoris/", views.favorites, name="favorites"),
    path("alertes/", views.create_alert, name="create_alert"),
]
