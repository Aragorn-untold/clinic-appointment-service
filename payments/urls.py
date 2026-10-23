from django.urls import include, path
from rest_framework.routers import DefaultRouter

from payments.views import PaymentViewSet, StripeCancelView, StripeSuccessView

router = DefaultRouter()

router.register("payments", PaymentViewSet, basename="payment")

urlpatterns = [
    path("success/", StripeSuccessView.as_view(), name="success"),
    path("cancel/", StripeCancelView.as_view(), name="cancel"),
    path("", include(router.urls)),
]

app_name = "payments"
