from django.urls import include, path
from rest_framework.routers import DefaultRouter

from payments import views

app_name = "payments"

router = DefaultRouter()
router.register("payments", views.PaymentViewSet, basename="payment")

urlpatterns = [
    path("", include(router.urls)),
    path("payments/success/", views.PaymentSuccessView.as_view(), name="success"),
    path("payments/cancel/", views.PaymentCancelView.as_view(), name="cancel"),
    path("payments/<int:pk>/renew/", views.renew_payment, name="renew"),
]
