from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.login_view, name="login"),
    path("connexion/activation/", views.activate_view, name="activate"),
    path("connexion/code/", views.verify_view, name="verify"),
    path("connexion/mot-de-passe/", views.set_password_view, name="set_password"),
    path("connexion/equipe/", views.staff_login_view, name="staff_login"),
    path("connexion/equipe/demo/", views.staff_demo_login_view, name="staff_demo_login"),
    path("deconnexion/", views.logout_view, name="logout"),
]
