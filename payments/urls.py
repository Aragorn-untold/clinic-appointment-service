from django.urls import path

from payments import views

app_name = "payments"

urlpatterns = [
    path("payments/success/", views.PaymentSuccessView.as_view(), name="success"),
    path("payments/cancel/", views.PaymentCancelView.as_view(), name="cancel"),
    path("payments/<int:pk>/renew/", views.renew_payment, name="renew"),
]
