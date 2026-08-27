from django.urls import path

from . import views

app_name = "profiles"

urlpatterns = [
    path("profil/", views.my_profile, name="mine"),
    path("profils/<int:pk>/", views.public_profile, name="public"),
]
