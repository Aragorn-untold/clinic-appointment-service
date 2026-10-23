from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from appointments.models import Appointment
from core.tests.base import PASSWORD, BaseTestCase
from doctor_slots.models import DoctorSlot
from payments.models import Payment

URL = "/appointments/"


@patch("appointments.serializers.notify_admins")
class UnpaidPaymentBookingTests(BaseTestCase):
    """A patient with an unpaid (PENDING or EXPIRED) payment cannot book."""

    def setUp(self):
        super().setUp()
        start = self.slot.start + timedelta(days=1)
        self.free_slot = DoctorSlot.objects.create(
            doctor=self.doctor,
            start=start,
            end=start + timedelta(minutes=30),
        )

    def create_payment(self, status):
        return Payment.objects.create(
            appointment=self.appointment,
            status=status,
            type=Payment.Type.CONSULTATION,
            session_id=f"sess_{status.lower()}",
            session_url="https://checkout.stripe.com/pay/sess_test",
            money_to_pay=self.appointment.price,
        )

    def book(self, client):
        return client.post(URL, {"doctor_slot": self.free_slot.id}, format="json")

    def test_unpaid_payment_blocks_booking(self, notify_mock):
        for status in (Payment.Status.PENDING, Payment.Status.EXPIRED):
            with self.subTest(status=status):
                payment = self.create_payment(status)

                response = self.book(self.auth_client)

                self.assertEqual(response.status_code, 400)
                self.assertIn("unpaid payment", str(response.data["non_field_errors"][0]))
                self.assertFalse(Appointment.objects.filter(doctor_slot=self.free_slot).exists())
                notify_mock.assert_not_called()
                payment.delete()

    def test_paid_payment_does_not_block_booking(self, notify_mock):
        self.create_payment(Payment.Status.PAID)

        response = self.book(self.auth_client)

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Appointment.objects.filter(doctor_slot=self.free_slot, patient=self.user).exists(),
        )

    def test_other_patients_unpaid_payment_does_not_block_booking(self, notify_mock):
        self.create_payment(Payment.Status.PENDING)
        other_patient = get_user_model().objects.create_user(
            email="other@example.com",
            password=PASSWORD,
        )
        client = APIClient()
        client.force_authenticate(user=other_patient)

        response = self.book(client)

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Appointment.objects.filter(doctor_slot=self.free_slot, patient=other_patient).exists(),
        )
