from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard, name="home"),
    path("profils/", views.profiles, name="profiles"),
    path("profils/<int:pk>/", views.profile_detail, name="profile_detail"),
    path("profils/<int:pk>/<str:action>/", views.user_action, name="user_action"),
    path("annonces/", views.listings, name="listings"),
    path("annonces/<int:pk>/<str:action>/", views.listing_action, name="listing_action"),
    path("signalements/", views.reports, name="reports"),
    path("signalements/<int:pk>/<str:action>/", views.report_action, name="report_action"),
    path("recommandations/", views.recommendations, name="recommendations"),
    path("messagerie/", views.team_messaging, name="staff_messaging"),
    path("conversations/", views.conversations, name="conversations"),
    path("conversations/<int:pk>/", views.conversation_detail, name="conversation_detail"),
    path("diffusions/", views.broadcast, name="broadcast"),
    path("alertes/", views.alerts, name="alerts"),
    path("journal/", views.activity_logs, name="activity_logs"),
]
