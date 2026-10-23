from django.urls import include, path
from rest_framework.routers import DefaultRouter

from specializations.views import SpecializationViewSet

router = DefaultRouter()
router.register("", SpecializationViewSet)

urlpatterns = [path("", include(router.urls))]

app_name = "specializations"
