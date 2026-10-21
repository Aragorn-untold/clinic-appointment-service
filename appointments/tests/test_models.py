from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from appointments.models import Appointment
from doctors.models import Doctor
from doctor_slots.models import DoctorSlot


class AppointmentTests(TestCase):
    def setUp(self):
        self.patient = get_user_model().objects.create_user(
            email="patient@example.com",
            password="test-password",
        )
        doctor = Doctor.objects.create(
            first_name="Olena",
            last_name="Kovalenko",
            price_per_visit=800,
        )
        start = timezone.now() + timedelta(days=1)
        self.slot = DoctorSlot.objects.create(
            doctor=doctor,
            start=start,
            end=start + timedelta(minutes=30),
        )
        self.appointment = Appointment.objects.create(
            doctor_slot=self.slot,
            patient=self.patient,
            price=Decimal("800.00"),
        )

    def test_slot_cannot_have_two_booked_appointments(self):
        another_patient = get_user_model().objects.create_user(
            email="another@example.com",
            password="test-password",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Appointment.objects.create(
                    doctor_slot=self.slot,
                    patient=another_patient,
                    price=Decimal("800.00"),
                )

    def test_patient_and_slot_are_protected_from_deletion(self):
        with self.assertRaises(ProtectedError):
            self.patient.delete()

        with self.assertRaises(ProtectedError):
            self.slot.delete()
