from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from appointments.models import Appointment
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
