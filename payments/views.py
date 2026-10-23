import stripe
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core import settings
from payments.models import Payment
from payments.serializers import PaymentSerializer

stripe.api_key = settings.STRIPE_SECRET_KEY


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Payment.objects.none()
        user = self.request.user
        return Payment.objects.filter(appointment__patient=user)


class StripeSuccessView(APIView):
    def get(self, request):
        session_id = request.GET.get("session_id")
        if not session_id:
            return Response({"error": "Session ID required"}, status=status.HTTP_400_BAD_REQUEST)

        payment = Payment.objects.filter(session_id=session_id).first()
        if not payment:
            return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            session = stripe.checkout.Session.retrieve(session_id)
            payment_status = (
                session.get("payment_status") if isinstance(session, dict) else getattr(session, "payment_status", None)
            )

            if payment_status == "paid":
                payment.status = Payment.Status.PAID
                payment.save()
                return Response({"status": Payment.Status.PAID}, status=status.HTTP_200_OK)
            return Response({"status": Payment.Status.PENDING}, status=status.HTTP_200_OK)
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class StripeCancelView(APIView):
    def get(self, request):
        return Response({"message": "The payment was cancelled."}, status=status.HTTP_200_OK)


class RenewPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)

        if payment.appointment.patient != request.user:
            return Response({"detail": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

        if payment.status != Payment.Status.EXPIRED:
            return Response({"detail": "Only EXPIRED payments can be renewed"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": f"{payment.type} Payment",
                            },
                            "unit_amount": int(payment.money_to_pay * 100),
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url=f"{settings.SITE_URL}/payments/success/?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.SITE_URL}/payments/cancel/",
            )

            payment.session_id = session.id
            payment.session_url = session.url
            payment.status = Payment.Status.PENDING
            payment.save()

            return Response(
                {"session_id": session.id, "session_url": session.url},
                status=status.HTTP_201_CREATED,
            )
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
