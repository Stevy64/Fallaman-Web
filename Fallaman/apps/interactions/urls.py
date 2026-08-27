from django.urls import path

from . import views

app_name = "interactions"

urlpatterns = [
    path("annonces/<int:pk>/interesse/", views.express, name="express"),
]
