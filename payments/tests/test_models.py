from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from appointments.models import Appointment
from core.tests.base import BaseTestCase
from doctor_slots.models import DoctorSlot
from doctors.models import Doctor
from payments.models import Payment


class PaymentTests(TestCase):
    def test_session_id_must_be_unique(self):
        patient = get_user_model().objects.create_user(
            email="patient@example.com",
            password="test-password",
        )
        doctor = Doctor.objects.create(
            first_name="Olena",
            last_name="Kovalenko",
            price_per_visit=800,
        )
        start = timezone.now() + timedelta(days=1)
        slot = DoctorSlot.objects.create(
            doctor=doctor,
            start=start,
            end=start + timedelta(minutes=30),
        )
        appointment = Appointment.objects.create(
            doctor_slot=slot,
            patient=patient,
            price=Decimal("800.00"),
        )

        payment_data = {
            "appointment": appointment,
            "type": Payment.Type.CONSULTATION,
            "session_url": "https://example.com/session",
            "session_id": "session-123",
            "money_to_pay": Decimal("800.00"),
        }
        Payment.objects.create(**payment_data)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.create(**payment_data)


class PaymentSessionUrlLengthTests(BaseTestCase):
    def test_accepts_long_stripe_checkout_url(self):
        # Real Stripe Checkout URLs are 400+ characters (they end with a long #fragment)
        long_url = "https://checkout.stripe.com/c/pay/cs_test_" + "a" * 60 + "#" + "f" * 500
        payment = Payment(
            appointment=self.appointment,
            type=Payment.Type.CONSULTATION,
            session_id="cs_test_long_url",
            session_url=long_url,
            money_to_pay=self.appointment.price,
        )

        payment.full_clean()
        payment.save()

        payment.refresh_from_db()
        self.assertEqual(payment.session_url, long_url)
