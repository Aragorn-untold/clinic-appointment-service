from django.urls import path

from appointments.views import AppointmentViewSet

app_name = "appointments"

urlpatterns = [
    path(
        "",
        AppointmentViewSet.as_view({"get": "list"}),
        name="appointment-list",
    ),
    path(
        "<int:pk>/",
        AppointmentViewSet.as_view({"get": "retrieve"}),
        name="appointment-detail",
    ),
]
