from django.urls import path, include
from rest_framework import routers

from doctor_slots.views import DoctorSlotsViewSet

router = routers.DefaultRouter()
router.register("slots", DoctorSlotsViewSet, basename="slot")
urlpatterns = [
    path("", include(router.urls)),
]

app_name = "doctor_slots"
