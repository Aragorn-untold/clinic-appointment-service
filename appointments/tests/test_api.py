from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from appointments.models import Appointment
from doctor_slots.models import DoctorSlot
from doctors.models import Doctor
from specializations.models import Specialization


class AppointmentAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.patient = User.objects.create_user(
            email="patient@example.com",
            password="testpass123",
        )
        self.other_patient = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
        )
        self.admin = User.objects.create_superuser(
            email="admin@example.com",
            password="testpass123",
        )

        self.specialization = Specialization.objects.create(
            name="Cardiology",
            code="cardiology",
        )
        self.doctor = Doctor.objects.create(
            first_name="Olena",
            last_name="Kovalenko",
            price_per_visit=Decimal("800.00"),
        )
        self.doctor.specializations.add(self.specialization)

        start = timezone.now() + timedelta(days=2)
        self.slot = DoctorSlot.objects.create(
            doctor=self.doctor,
            start=start,
            end=start + timedelta(minutes=30),
        )
        self.appointment = Appointment.objects.create(
            doctor_slot=self.slot,
            patient=self.patient,
            price=Decimal("800.00"),
        )

        self.client = APIClient()
        self.list_url = "/appointments/"

    def test_patient_sees_only_own_appointments(self):
        self.client.force_authenticate(user=self.patient)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.appointment.id)

    def test_admin_sees_all_appointments(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_patient_can_view_own_appointment_details(self):
        self.client.force_authenticate(user=self.patient)

        response = self.client.get(f"{self.list_url}{self.appointment.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("doctor_slot", response.data)
        self.assertEqual(
            response.data["doctor_slot"]["doctor"]["first_name"],
            "Olena",
        )

    def test_patient_cannot_view_another_patients_appointment(self):
        self.client.force_authenticate(user=self.other_patient)

        response = self.client.get(f"{self.list_url}{self.appointment.id}/")

        self.assertEqual(response.status_code, 404)

    def test_filter_by_status(self):
        self.client.force_authenticate(user=self.patient)

        response = self.client.get(
            self.list_url,
            {"status": Appointment.Status.BOOKED},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_invalid_status_returns_400(self):
        self.client.force_authenticate(user=self.patient)

        response = self.client.get(
            self.list_url,
            {"status": "INVALID"},
        )

        self.assertEqual(response.status_code, 400)
