from django.urls import path

from appointments.views import AppointmentViewSet

app_name = "appointments"

urlpatterns = [
    path(
        "",
        AppointmentViewSet.as_view(
            {
                "get": "list",
                "post": "create",
            }
        ),
        name="appointment-list",
    ),
    path(
        "<int:pk>/",
        AppointmentViewSet.as_view({"get": "retrieve"}),
        name="appointment-detail",
    ),
    path(
        "<int:pk>/cancel/",
        AppointmentViewSet.as_view({"post": "cancel"}),
        name="appointment-cancel",
    ),
    path(
        "<int:pk>/complete/",
        AppointmentViewSet.as_view({"post": "complete"}),
        name="appointment-complete",
    ),
    path(
        "<int:pk>/no-show/",
        AppointmentViewSet.as_view({"post": "no_show"}),
        name="appointment-no-show",
    ),
]
