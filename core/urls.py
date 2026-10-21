from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularSwaggerView, SpectacularAPIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Schema
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger",
    ),
    # Token
    path("api/token/", TokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    # Local
    path("users/", include("users.urls", namespace="users")),
    path("specializations/", include("specializations.urls", namespace="specializations")),
    path("doctors/", include("doctors.urls", namespace="doctors")),
    path("slots/", include("doctor_slots.urls", namespace="doctor_slots")),
    path("appointments/", include("appointments.urls", namespace="appointments")),
    path("", include("payments.urls", namespace="payments")),
]
