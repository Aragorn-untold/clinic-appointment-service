import stripe
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core import settings
from payments.models import Payment
from payments.serializers import PaymentSerializer

stripe.api_key = settings.STRIPE_SECRET_KEY


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Payment.objects.all()

        return Payment.objects.filter(appointment__patient=user)


class StripeSuccessView(APIView):
    def get(self, request):
        session_id = request.GET.get("session_id")
        if not session_id:
            return Response({"error": "Session ID required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = stripe.checkout.Session.retrieve(session_id)
            payment_status = (
                session.get("payment_status") if isinstance(session, dict) else getattr(session, "payment_status", None)
            )

            if payment_status == "paid":
                payment = Payment.objects.filter(session_id=session_id).first()
                if payment:
                    payment.status = "PAID"
                    payment.save()
                    return Response({"message": "Payment successful!"}, status=status.HTTP_200_OK)
                return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)
            return Response({"message": "Payment not completed yet"}, status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class StripeCancelView(APIView):
    def get(self, request):
        return Response({"message": "The payment was cancelled."}, status=status.HTTP_200_OK)
