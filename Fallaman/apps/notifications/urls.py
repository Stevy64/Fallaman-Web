from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("notifications/", views.notification_list, name="list"),
    path("notifications/lues/", views.mark_all_read, name="read"),
    path("notifications/<int:pk>/ouvrir/", views.open_notification, name="open"),
    path("notifications/<int:pk>/supprimer/", views.delete_notification, name="delete"),
]
