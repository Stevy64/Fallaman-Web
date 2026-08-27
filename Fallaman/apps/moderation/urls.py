from django.urls import path

from . import views

app_name = "moderation"

urlpatterns = [
    path("annonces/<int:pk>/signaler/", views.report_listing, name="report"),
    path("bloquer/<int:pk>/", views.block_user, name="block"),
    path("debloquer/<int:pk>/", views.unblock_user, name="unblock"),
]
