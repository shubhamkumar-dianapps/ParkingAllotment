from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("park/", views.select_vehicle, name="select_vehicle"),
    path("slots/<str:vehicle_type>/", views.view_slots, name="view_slots"),
    path("vehicle/<int:slot_id>/", views.vehicle_form, name="vehicle_form"),
    path("checkout/", views.checkout, name="checkout"),
    path("token/<int:ticket_id>/", views.token_success, name="token_success"),
    path("download/pdf/<int:ticket_id>/", views.download_pdf, name="download_pdf"),
]
