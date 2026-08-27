from django.urls import path

from . import views

app_name = "taxonomy"

urlpatterns = [
    path("categories/", views.category_list, name="list"),
    path("categories/<slug:slug>/", views.category_detail, name="detail"),
]
