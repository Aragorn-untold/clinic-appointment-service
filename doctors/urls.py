from django.urls import include, path
from rest_framework import routers

from doctors.views import DoctorViewSet

router = routers.DefaultRouter()
router.register("", DoctorViewSet)

urlpatterns = [path("", include(router.urls))]

app_name = "doctors"
