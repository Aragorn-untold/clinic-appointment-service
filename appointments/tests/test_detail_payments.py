from datetime import timedelta

from django.urls import reverse
from rest_framework import status

from appointments.models import Appointment
from core.tests.base import BaseTestCase
from doctor_slots.models import DoctorSlot
from payments.models import Payment


class AppointmentDetailPaymentsTests(BaseTestCase):
    """Task 10.3: AppointmentDetailSerializer includes the appointment's payments."""

    def setUp(self):
        super().setUp()
        self.url = reverse("appointments:appointment-detail", kwargs={"pk": self.appointment.pk})

    def test_detail_includes_payments(self):
        payment = Payment.objects.create(
            appointment=self.appointment,
            type=Payment.Type.CONSULTATION,
            status=Payment.Status.PENDING,
            session_id="cs_test_detail_1",
            session_url="https://checkout.stripe.com/c/pay/cs_test_detail_1",
            money_to_pay=self.appointment.price,
        )

        res = self.auth_client.get(self.url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["payments"]), 1)
        self.assertEqual(res.data["payments"][0]["id"], payment.id)
        self.assertEqual(res.data["payments"][0]["session_url"], payment.session_url)

    def test_detail_without_payments_returns_empty_list(self):
        res = self.auth_client.get(self.url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["payments"], [])

    def test_detail_shows_only_this_appointments_payments(self):
        other_slot = DoctorSlot.objects.create(
            doctor=self.doctor,
            start=self.slot.end,
            end=self.slot.end + timedelta(minutes=30),
        )
        other_appointment = Appointment.objects.create(
            doctor_slot=other_slot, patient=self.user, price=self.appointment.price
        )
        Payment.objects.create(
            appointment=other_appointment,
            type=Payment.Type.CONSULTATION,
            status=Payment.Status.PENDING,
            session_id="cs_test_detail_other",
            session_url="https://checkout.stripe.com/c/pay/cs_test_detail_other",
            money_to_pay=other_appointment.price,
        )

        res = self.auth_client.get(self.url)

        self.assertEqual(res.data["payments"], [])
