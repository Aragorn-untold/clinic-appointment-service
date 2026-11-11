from datetime import timedelta
from unittest.mock import MagicMock, patch

import stripe
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from kombu.exceptions import OperationalError
from rest_framework import status
from rest_framework.test import APIClient

from appointments.models import Appointment
from core.tests.base import PASSWORD, BaseTestCase
from doctor_slots.models import DoctorSlot
from notifications.services import notify_admins as real_notify_admins
from payments.models import Payment


def action_url(name, appointment_id):
    return reverse(f"appointments:appointment-{name}", kwargs={"pk": appointment_id})


class AppointmentStatusActionPermissionTests(BaseTestCase):
    """Task 5.1: who can call cancel / complete / no-show and how errors map
    to status codes. Services are mocked, so no Stripe or Telegram calls."""

    def setUp(self):
        super().setUp()
        self.other_user = get_user_model().objects.create_user(email="other@example.com", password=PASSWORD)
        self.other_client = APIClient()
        self.other_client.force_authenticate(user=self.other_user)

    def mock_service(self, name, **kwargs):
        patcher = patch(f"appointments.services.{name}", **kwargs)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def mock_service_returning_appointment(self, name):
        return self.mock_service(name, side_effect=lambda appointment, request=None: appointment)

    # cancel

    def test_owner_can_cancel(self):
        mock = self.mock_service_returning_appointment("cancel_appointment")

        res = self.auth_client.post(action_url("cancel", self.appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["id"], self.appointment.pk)
        self.assertIn("payments", res.data)
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0].pk, self.appointment.pk)

    def test_admin_can_cancel_any_appointment(self):
        self.mock_service_returning_appointment("cancel_appointment")

        res = self.admin_client.post(action_url("cancel", self.appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_other_patient_gets_404_on_cancel(self):
        mock = self.mock_service_returning_appointment("cancel_appointment")

        res = self.other_client.post(action_url("cancel", self.appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        mock.assert_not_called()

    def test_anonymous_cannot_cancel(self):
        mock = self.mock_service_returning_appointment("cancel_appointment")

        res = self.client.post(action_url("cancel", self.appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        mock.assert_not_called()

    def test_cancel_wrong_status_returns_400(self):
        self.mock_service("cancel_appointment", side_effect=ValueError("Only booked appointments can be cancelled."))

        res = self.auth_client.post(action_url("cancel", self.appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["detail"], "Only booked appointments can be cancelled.")

    def test_get_on_action_not_allowed(self):
        res = self.auth_client.get(action_url("cancel", self.appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # complete

    def test_admin_can_complete(self):
        mock = self.mock_service_returning_appointment("complete_appointment")

        res = self.admin_client.post(action_url("complete", self.appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("payments", res.data)
        mock.assert_called_once()

    def test_patient_cannot_complete(self):
        mock = self.mock_service_returning_appointment("complete_appointment")

        res = self.auth_client.post(action_url("complete", self.appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        mock.assert_not_called()

    def test_anonymous_cannot_complete(self):
        res = self.client.post(action_url("complete", self.appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_complete_unknown_appointment_returns_404(self):
        res = self.admin_client.post(action_url("complete", 999999))

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_complete_wrong_status_returns_400(self):
        self.mock_service("complete_appointment", side_effect=ValueError("Only booked appointments can be completed."))
        res = self.admin_client.post(action_url("complete", self.appointment.pk))
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_mark_no_show(self):
        mock = self.mock_service_returning_appointment("mark_no_show")

        res = self.admin_client.post(action_url("no-show", self.appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        mock.assert_called_once()

    def test_patient_cannot_mark_no_show(self):
        mock = self.mock_service_returning_appointment("mark_no_show")

        res = self.auth_client.post(action_url("no-show", self.appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        mock.assert_not_called()

    def test_no_show_wrong_status_returns_400(self):
        self.mock_service("mark_no_show", side_effect=ValueError("Only booked appointments can be marked as no-show."))

        res = self.admin_client.post(action_url("no-show", self.appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class AppointmentStatusActionFlowTests(BaseTestCase):
    """Task 5.1: real services end to end, with Stripe and Telegram mocked.

    The status is saved in the request; the Stripe payment is created by a Celery task
    after commit. captureOnCommitCallbacks(execute=True) runs that task inline (eager).
    """

    def setUp(self):
        super().setUp()
        stripe_patcher = patch("payments.services.stripe.checkout.Session.create")
        self.mock_stripe_create = stripe_patcher.start()
        self.addCleanup(stripe_patcher.stop)
        self.mock_stripe_create.side_effect = lambda **kwargs: MagicMock(
            id=f"cs_test_{self.mock_stripe_create.call_count}",
            url=f"https://checkout.stripe.com/c/pay/cs_test_{self.mock_stripe_create.call_count}",
        )

        notify_patcher = patch("appointments.services.notify_admins")
        self.mock_notify = notify_patcher.start()
        self.addCleanup(notify_patcher.stop)

    def create_appointment(self, starts_in):
        start = timezone.now().replace(microsecond=0) + starts_in
        slot = DoctorSlot.objects.create(doctor=self.doctor, start=start, end=start + timedelta(minutes=30))
        return Appointment.objects.create(doctor_slot=slot, patient=self.user, price=self.doctor.price_per_visit)

    def test_complete_creates_consultation_payment(self):
        with self.captureOnCommitCallbacks(execute=True):
            res = self.admin_client.post(action_url("complete", self.appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], Appointment.Status.COMPLETED)
        self.assertIsNotNone(res.data["completed_at"])
        # The payment is created after the response, by the Celery task
        self.assertEqual(res.data["payments"], [])
        payment = Payment.objects.get(appointment=self.appointment)
        self.assertEqual(payment.type, Payment.Type.CONSULTATION)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.mock_notify.assert_called_once()

        detail = self.auth_client.get(reverse("appointments:appointment-detail", kwargs={"pk": self.appointment.pk}))
        self.assertEqual(len(detail.data["payments"]), 1)
        self.assertEqual(detail.data["payments"][0]["session_url"], payment.session_url)

    def test_complete_twice_returns_400(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.admin_client.post(action_url("complete", self.appointment.pk))

        with self.captureOnCommitCallbacks(execute=True):
            res = self.admin_client.post(action_url("complete", self.appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Payment.objects.filter(appointment=self.appointment).count(), 1)

    def test_cancel_more_than_24h_ahead_is_free(self):
        appointment = self.create_appointment(timedelta(days=3))

        with self.captureOnCommitCallbacks(execute=True):
            res = self.auth_client.post(action_url("cancel", appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], Appointment.Status.CANCELLED)
        self.assertFalse(Payment.objects.filter(appointment=appointment).exists())
        self.mock_stripe_create.assert_not_called()

    def test_cancel_less_than_24h_ahead_creates_fee(self):
        appointment = self.create_appointment(timedelta(hours=2))

        with self.captureOnCommitCallbacks(execute=True):
            res = self.auth_client.post(action_url("cancel", appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], Appointment.Status.CANCELLED)
        payment = Payment.objects.get(appointment=appointment)
        self.assertEqual(payment.type, Payment.Type.CANCELLATION_FEE)

    def test_cancel_after_appointment_ended_returns_400(self):
        appointment = self.create_appointment(-timedelta(hours=2))

        res = self.auth_client.post(action_url("cancel", appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.BOOKED)
        self.assertFalse(Payment.objects.filter(appointment=appointment).exists())
        self.mock_stripe_create.assert_not_called()
        self.mock_notify.assert_not_called()

    def test_cancel_appointment_in_progress_returns_400(self):
        appointment = self.create_appointment(-timedelta(minutes=10))

        res = self.auth_client.post(action_url("cancel", appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.BOOKED)
        self.assertFalse(Payment.objects.filter(appointment=appointment).exists())
        self.mock_stripe_create.assert_not_called()

    def test_no_show_creates_fee(self):
        missed = self.create_appointment(-timedelta(hours=2))

        with self.captureOnCommitCallbacks(execute=True):
            res = self.admin_client.post(action_url("no-show", missed.pk))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], Appointment.Status.NO_SHOW)
        payment = Payment.objects.get(appointment=missed)
        self.assertEqual(payment.type, Payment.Type.NO_SHOW_FEE)

    @patch("appointments.services.create_appointment_payment")
    def test_stripe_down_still_completes_appointment(self, payment_task):
        # Stripe is not called during the request any more, so its outage can't block the status change
        self.mock_stripe_create.side_effect = stripe.error.APIConnectionError("Stripe is down")

        with self.captureOnCommitCallbacks(execute=True):
            res = self.admin_client.post(action_url("complete", self.appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.COMPLETED)
        self.mock_stripe_create.assert_not_called()
        payment_task.delay.assert_called_once_with(self.appointment.pk, Payment.Type.CONSULTATION)
        self.mock_notify.assert_called_once()

    @patch("appointments.services.create_appointment_payment")
    def test_complete_succeeds_when_notification_cannot_be_queued(self, payment_task):
        # Use the real notify_admins, with Redis failing when the message is queued
        with (
            patch("appointments.services.notify_admins", wraps=real_notify_admins),
            patch(
                "notifications.services.send_telegram_message_task.delay",
                side_effect=OperationalError("Redis is down"),
            ) as mock_delay,
            self.assertLogs("notifications.services", level="ERROR"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            res = self.admin_client.post(action_url("complete", self.appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.COMPLETED)
        mock_delay.assert_called_once()
        payment_task.delay.assert_called_once_with(self.appointment.pk, Payment.Type.CONSULTATION)

    @patch("appointments.services.create_appointment_payment")
    def test_no_show_for_future_appointment_returns_400(self, payment_task):
        # self.appointment is tomorrow
        with self.captureOnCommitCallbacks(execute=True):
            res = self.admin_client.post(action_url("no-show", self.appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["detail"], "Only appointments that have already ended can be marked as no-show.")
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.BOOKED)
        payment_task.delay.assert_not_called()
        self.mock_notify.assert_not_called()

    @patch("appointments.services.create_appointment_payment")
    def test_no_show_for_appointment_in_progress_returns_400(self, payment_task):
        appointment = self.create_appointment(-timedelta(minutes=10))

        with self.captureOnCommitCallbacks(execute=True):
            res = self.admin_client.post(action_url("no-show", appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.BOOKED)
        payment_task.delay.assert_not_called()

    @patch("appointments.services.create_appointment_payment")
    def test_failed_status_change_queues_no_payment(self, payment_task):
        appointment = self.create_appointment(timedelta(days=3))
        appointment.status = Appointment.Status.CANCELLED
        appointment.save(update_fields=["status"])

        with self.captureOnCommitCallbacks(execute=True):
            res = self.admin_client.post(action_url("complete", appointment.pk))

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        payment_task.delay.assert_not_called()
