from django.urls import path

from . import views

urlpatterns = [
    path("gateway/ussd", views.ussd, name="gateway-ussd"),
    path("gateway/whatsapp", views.whatsapp, name="gateway-whatsapp"),
]
