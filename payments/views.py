<<<<<<< HEAD
import stripe
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.models import Payment
from payments.serializers import PaymentSerializer
from payments.services import PaymentService


class PaymentSuccessView(APIView):
    permission_classes = []

    def get(self, request):
        session_id = request.query_params.get("session_id")
        if not session_id:
            return Response(
                {"detail": "session_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = get_object_or_404(Payment, session_id=session_id)

        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except stripe.error.StripeError as exc:
            return Response(
                {"detail": f"Stripe error: {exc.user_message or str(exc)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if session.payment_status == "paid" and payment.status != Payment.Status.PAID:
            payment.status = Payment.Status.PAID
            payment.save(update_fields=["status"])

        return Response(PaymentSerializer(payment).data)


class PaymentCancelView(APIView):
    permission_classes = []

    def get(self, request):
        return Response({"detail": "Payment cancelled. The session remains valid for 24 hours."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def renew_payment(request, pk):
    payment = get_object_or_404(Payment, pk=pk)

    appointment_owner = getattr(payment.appointment, "patient", getattr(payment.appointment, "user", None))
    if appointment_owner != request.user:
        return Response(
            {"detail": "You do not have permission to renew this payment."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if payment.status != Payment.Status.EXPIRED:
        return Response(
            {"detail": "Only EXPIRED payments can be renewed."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    new_payment = PaymentService.create_payment_for_appointment(
        appointment=payment.appointment,
        payment_type=payment.type,
        request=request,
    )
    return Response(PaymentSerializer(new_payment).data, status=status.HTTP_201_CREATED)
=======
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from payments.models import Payment
from payments.serializers import PaymentSerializer


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Payment.objects.all()

        return Payment.objects.filter(appointment__patient=user)
>>>>>>> dd05545c72bcc2a1586771fd3d8cf105d89e0661
