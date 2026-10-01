from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("paiements/singpay/callback/", views.singpay_callback, name="callback"),
    path("paiements/retour/<uuid:public_id>/", views.payment_return, name="return"),
]
