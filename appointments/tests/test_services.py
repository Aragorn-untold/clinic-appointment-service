from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from appointments.models import Appointment
from appointments.services import (
    cancel_appointment,
    complete_appointment,
    mark_no_show,
)
from doctor_slots.models import DoctorSlot
from doctors.models import Doctor
from notifications.messages import (
    appointment_cancelled,
    appointment_completed,
    appointment_no_show,
)
from payments.models import Payment


class AppointmentServiceTestsBase(TestCase):
    def setUp(self):
        self.patient = get_user_model().objects.create_user(
            email="patient@example.com",
            password="test-password",
        )
        self.doctor = Doctor.objects.create(
            first_name="Olena",
            last_name="Kovalenko",
            price_per_visit=Decimal("800.00"),
        )
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


class CancelAppointmentTests(AppointmentServiceTestsBase):
    @patch("appointments.services.notify_admins")
    def test_cancel_more_than_24_hours_before_without_fee(self, notify_mock):
        cancel_appointment(self.appointment)

        self.appointment.refresh_from_db()
        self.assertEqual(
            self.appointment.status,
            Appointment.Status.CANCELLED,
        )
        self.assertFalse(
            Payment.objects.filter(
                appointment=self.appointment,
                type=Payment.Type.CANCELLATION_FEE,
            ).exists()
        )
        notify_mock.assert_called_once_with(
            appointment_cancelled(self.appointment)
        )

    @patch("appointments.services.PaymentService.create_payment_for_appointment")
    @patch("appointments.services.notify_admins")
    def test_cancel_less_than_24_hours_before_creates_fee(
        self,
        notify_mock,
        payment_mock,
    ):
        self.slot.start = timezone.now() + timedelta(hours=12)
        self.slot.save()

        cancel_appointment(self.appointment)

        payment_mock.assert_called_once_with(
            self.appointment,
            Payment.Type.CANCELLATION_FEE,
            None,
        )
        self.appointment.refresh_from_db()
        self.assertEqual(
            self.appointment.status,
            Appointment.Status.CANCELLED,
        )
        notify_mock.assert_called_once()

    @patch("appointments.services.notify_admins")
    def test_cannot_cancel_already_cancelled_appointment(self, notify_mock):
        self.appointment.status = Appointment.Status.CANCELLED
        self.appointment.save(update_fields=["status"])

        with self.assertRaises(ValueError):
            cancel_appointment(self.appointment)

        notify_mock.assert_not_called()


class CompleteAppointmentTests(AppointmentServiceTestsBase):
    @patch("appointments.services.PaymentService.create_payment_for_appointment")
    @patch("appointments.services.notify_admins")
    def test_complete_appointment_creates_payment_and_sets_completion_time(
        self,
        notify_mock,
        payment_mock,
    ):
        completed_before = timezone.now()

        complete_appointment(self.appointment)

        self.appointment.refresh_from_db()

        self.assertEqual(
            self.appointment.status,
            Appointment.Status.COMPLETED,
        )
        self.assertIsNotNone(self.appointment.completed_at)
        self.assertGreaterEqual(
            self.appointment.completed_at,
            completed_before,
        )
        payment_mock.assert_called_once_with(
            self.appointment,
            Payment.Type.CONSULTATION,
            None,
        )
        notify_mock.assert_called_once_with(
            appointment_completed(self.appointment)
        )

    @patch("appointments.services.PaymentService.create_payment_for_appointment")
    @patch("appointments.services.notify_admins")
    def test_cannot_complete_cancelled_appointment(
        self,
        notify_mock,
        payment_mock,
    ):
        self.appointment.status = Appointment.Status.CANCELLED
        self.appointment.save(update_fields=["status"])

        with self.assertRaises(ValueError):
            complete_appointment(self.appointment)

        payment_mock.assert_not_called()
        notify_mock.assert_not_called()


class MarkNoShowTests(AppointmentServiceTestsBase):
    @patch("appointments.services.PaymentService.create_payment_for_appointment")
    @patch("appointments.services.notify_admins")
    def test_mark_no_show_creates_fee_and_updates_status(
        self,
        notify_mock,
        payment_mock,
    ):
        mark_no_show(self.appointment)

        self.appointment.refresh_from_db()

        self.assertEqual(
            self.appointment.status,
            Appointment.Status.NO_SHOW,
        )
        payment_mock.assert_called_once_with(
            self.appointment,
            Payment.Type.NO_SHOW_FEE,
            None,
        )
        notify_mock.assert_called_once_with(
            appointment_no_show(self.appointment)
        )

    @patch("appointments.services.PaymentService.create_payment_for_appointment")
    @patch("appointments.services.notify_admins")
    def test_cannot_mark_cancelled_appointment_as_no_show(
        self,
        notify_mock,
        payment_mock,
    ):
        self.appointment.status = Appointment.Status.CANCELLED
        self.appointment.save(update_fields=["status"])

        with self.assertRaises(ValueError):
            mark_no_show(self.appointment)

        payment_mock.assert_not_called()
        notify_mock.assert_not_called()
