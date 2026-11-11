from datetime import timedelta
from unittest.mock import patch

from django.db import transaction
from django.utils import timezone

from appointments.models import Appointment
from appointments.services import (
    cancel_appointment,
    complete_appointment,
    mark_no_show,
)
from core.tests.base import BaseTestCase
from notifications.messages import (
    appointment_cancelled,
    appointment_completed,
    appointment_no_show,
)
from payments.models import Payment

# Services save the status first and queue the Stripe payment in Celery after commit.
# TestCase never commits, so tests run the queued callbacks with captureOnCommitCallbacks.
PAYMENT_TASK = "appointments.services.create_appointment_payment"


class CancelAppointmentTests(BaseTestCase):
    @patch("appointments.services.timezone.now")
    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_cancel_more_than_24_hours_before_without_fee(
        self,
        notify_mock,
        payment_task,
        now_mock,
    ):
        # self.slot starts slightly less than 24h from now, so fake a time well outside the fee window
        now_mock.return_value = self.slot.start - timedelta(hours=25)

        with self.captureOnCommitCallbacks(execute=True):
            cancel_appointment(self.appointment)

        self.appointment.refresh_from_db()
        self.assertEqual(
            self.appointment.status,
            Appointment.Status.CANCELLED,
        )
        payment_task.delay.assert_not_called()
        self.assertFalse(
            Payment.objects.filter(
                appointment=self.appointment,
                type=Payment.Type.CANCELLATION_FEE,
            ).exists()
        )
        notify_mock.assert_called_once_with(appointment_cancelled(self.appointment))

    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_cancel_less_than_24_hours_before_creates_fee(
        self,
        notify_mock,
        payment_task,
    ):
        self.slot.start = timezone.now() + timedelta(hours=12)
        self.slot.save()

        with self.captureOnCommitCallbacks(execute=True):
            cancel_appointment(self.appointment)

        payment_task.delay.assert_called_once_with(
            self.appointment.pk,
            Payment.Type.CANCELLATION_FEE,
        )
        self.appointment.refresh_from_db()
        self.assertEqual(
            self.appointment.status,
            Appointment.Status.CANCELLED,
        )
        notify_mock.assert_called_once()

    @patch("appointments.services.timezone.now")
    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_cancel_exactly_24_hours_before_without_fee(
        self,
        notify_mock,
        payment_task,
        now_mock,
    ):
        now = self.slot.start - timedelta(hours=24)
        now_mock.return_value = now

        with self.captureOnCommitCallbacks(execute=True):
            cancel_appointment(self.appointment)

        payment_task.delay.assert_not_called()
        self.appointment.refresh_from_db()
        self.assertEqual(
            self.appointment.status,
            Appointment.Status.CANCELLED,
        )
        notify_mock.assert_called_once()

    @patch("appointments.services.timezone.now")
    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_cancel_24_hours_minus_one_second_before_creates_fee(
        self,
        notify_mock,
        payment_task,
        now_mock,
    ):
        now_mock.return_value = self.slot.start - timedelta(hours=24) + timedelta(seconds=1)

        with self.captureOnCommitCallbacks(execute=True):
            cancel_appointment(self.appointment)

        payment_task.delay.assert_called_once_with(
            self.appointment.pk,
            Payment.Type.CANCELLATION_FEE,
        )
        self.appointment.refresh_from_db()
        self.assertEqual(
            self.appointment.status,
            Appointment.Status.CANCELLED,
        )
        notify_mock.assert_called_once()

    @patch("appointments.services.timezone.now")
    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_cannot_cancel_after_appointment_ended(
        self,
        notify_mock,
        payment_task,
        now_mock,
    ):
        now_mock.return_value = self.slot.end + timedelta(hours=2)

        with self.captureOnCommitCallbacks(execute=True), self.assertRaises(ValueError):
            cancel_appointment(self.appointment)

        payment_task.delay.assert_not_called()
        notify_mock.assert_not_called()
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.BOOKED)

    @patch("appointments.services.timezone.now")
    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_cannot_cancel_appointment_in_progress(
        self,
        notify_mock,
        payment_task,
        now_mock,
    ):
        now_mock.return_value = self.slot.start + timedelta(minutes=10)

        with self.captureOnCommitCallbacks(execute=True), self.assertRaises(ValueError):
            cancel_appointment(self.appointment)

        payment_task.delay.assert_not_called()
        notify_mock.assert_not_called()
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.BOOKED)

    @patch("appointments.services.timezone.now")
    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_cannot_cancel_exactly_at_start(
        self,
        notify_mock,
        payment_task,
        now_mock,
    ):
        now_mock.return_value = self.slot.start

        with self.captureOnCommitCallbacks(execute=True), self.assertRaises(ValueError):
            cancel_appointment(self.appointment)

        payment_task.delay.assert_not_called()
        notify_mock.assert_not_called()

    @patch("appointments.services.timezone.now")
    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_cancel_one_second_before_start_creates_fee(
        self,
        notify_mock,
        payment_task,
        now_mock,
    ):
        now_mock.return_value = self.slot.start - timedelta(seconds=1)

        with self.captureOnCommitCallbacks(execute=True):
            cancel_appointment(self.appointment)

        payment_task.delay.assert_called_once_with(
            self.appointment.pk,
            Payment.Type.CANCELLATION_FEE,
        )
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.CANCELLED)
        notify_mock.assert_called_once()

    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_cannot_cancel_already_cancelled_appointment(self, notify_mock, payment_task):
        self.appointment.status = Appointment.Status.CANCELLED
        self.appointment.save(update_fields=["status"])

        with self.captureOnCommitCallbacks(execute=True), self.assertRaises(ValueError):
            cancel_appointment(self.appointment)

        payment_task.delay.assert_not_called()
        notify_mock.assert_not_called()


class CompleteAppointmentTests(BaseTestCase):
    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_complete_appointment_queues_payment_and_sets_completion_time(
        self,
        notify_mock,
        payment_task,
    ):
        completed_before = timezone.now()

        with self.captureOnCommitCallbacks(execute=True):
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
        payment_task.delay.assert_called_once_with(
            self.appointment.pk,
            Payment.Type.CONSULTATION,
        )
        notify_mock.assert_called_once_with(appointment_completed(self.appointment))

    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_payment_is_queued_only_after_commit(self, notify_mock, payment_task):
        with self.captureOnCommitCallbacks() as callbacks:
            complete_appointment(self.appointment)
            # Still inside the transaction: nothing is sent to Celery yet
            payment_task.delay.assert_not_called()

        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        payment_task.delay.assert_called_once_with(self.appointment.pk, Payment.Type.CONSULTATION)

    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_status_is_saved_before_payment_task_runs(self, notify_mock, payment_task):
        seen_statuses = []
        payment_task.delay.side_effect = lambda appointment_id, payment_type: seen_statuses.append(
            Appointment.objects.get(pk=appointment_id).status
        )

        with self.captureOnCommitCallbacks(execute=True):
            complete_appointment(self.appointment)

        self.assertEqual(seen_statuses, [Appointment.Status.COMPLETED])

    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_no_payment_queued_when_transaction_rolls_back(self, notify_mock, payment_task):
        # e.g. the view's transaction fails after the service ran
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    complete_appointment(self.appointment)
                    raise RuntimeError("rollback")
            except RuntimeError:
                pass

        payment_task.delay.assert_not_called()
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.BOOKED)

    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_cannot_complete_cancelled_appointment(
        self,
        notify_mock,
        payment_task,
    ):
        self.appointment.status = Appointment.Status.CANCELLED
        self.appointment.save(update_fields=["status"])

        with self.captureOnCommitCallbacks(execute=True), self.assertRaises(ValueError):
            complete_appointment(self.appointment)

        payment_task.delay.assert_not_called()
        notify_mock.assert_not_called()


class MarkNoShowTests(BaseTestCase):
    @patch("appointments.services.timezone.now")
    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_mark_no_show_queues_fee_and_updates_status(
        self,
        notify_mock,
        payment_task,
        now_mock,
    ):
        now_mock.return_value = self.slot.end + timedelta(hours=1)

        with self.captureOnCommitCallbacks(execute=True):
            mark_no_show(self.appointment)

        self.appointment.refresh_from_db()

        self.assertEqual(
            self.appointment.status,
            Appointment.Status.NO_SHOW,
        )
        payment_task.delay.assert_called_once_with(
            self.appointment.pk,
            Payment.Type.NO_SHOW_FEE,
        )
        notify_mock.assert_called_once_with(appointment_no_show(self.appointment))

    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_cannot_mark_future_appointment_as_no_show(self, notify_mock, payment_task):
        # self.slot is tomorrow
        with self.captureOnCommitCallbacks(execute=True), self.assertRaises(ValueError):
            mark_no_show(self.appointment)

        payment_task.delay.assert_not_called()
        notify_mock.assert_not_called()
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.BOOKED)

    @patch("appointments.services.timezone.now")
    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_cannot_mark_appointment_in_progress_as_no_show(self, notify_mock, payment_task, now_mock):
        now_mock.return_value = self.slot.start + timedelta(minutes=10)

        with self.captureOnCommitCallbacks(execute=True), self.assertRaises(ValueError):
            mark_no_show(self.appointment)

        payment_task.delay.assert_not_called()
        notify_mock.assert_not_called()
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.BOOKED)

    @patch("appointments.services.timezone.now")
    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_cannot_mark_no_show_one_second_before_end(self, notify_mock, payment_task, now_mock):
        now_mock.return_value = self.slot.end - timedelta(seconds=1)

        with self.captureOnCommitCallbacks(execute=True), self.assertRaises(ValueError):
            mark_no_show(self.appointment)

        payment_task.delay.assert_not_called()

    @patch("appointments.services.timezone.now")
    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_can_mark_no_show_exactly_at_end(self, notify_mock, payment_task, now_mock):
        now_mock.return_value = self.slot.end

        with self.captureOnCommitCallbacks(execute=True):
            mark_no_show(self.appointment)

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.NO_SHOW)
        payment_task.delay.assert_called_once_with(self.appointment.pk, Payment.Type.NO_SHOW_FEE)

    @patch(PAYMENT_TASK)
    @patch("appointments.services.notify_admins")
    def test_cannot_mark_cancelled_appointment_as_no_show(
        self,
        notify_mock,
        payment_task,
    ):
        self.appointment.status = Appointment.Status.CANCELLED
        self.appointment.save(update_fields=["status"])

        with self.captureOnCommitCallbacks(execute=True), self.assertRaises(ValueError):
            mark_no_show(self.appointment)

        payment_task.delay.assert_not_called()
        notify_mock.assert_not_called()
