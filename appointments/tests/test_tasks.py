from datetime import timedelta
from unittest.mock import patch

from django.db import DatabaseError
from django.test import override_settings
from django.utils import timezone

from appointments import services
from appointments.models import Appointment
from appointments.tasks import mark_no_shows
from core.tests.base import BaseTestCase
from doctor_slots.models import DoctorSlot
from payments.models import Payment


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
@patch("notifications.tasks.send_telegram_message")
class MarkNoShowsTaskTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        # real mark_no_show queues a Celery task that calls Stripe: never run it in tests
        patcher = patch("appointments.services.create_appointment_payment")
        self.mock_payment = patcher.start()
        self.addCleanup(patcher.stop)

    def _make_past_appointment(self, hours_ago=1, **kwargs):
        end = timezone.now() - timedelta(hours=hours_ago)
        slot = DoctorSlot.objects.create(
            doctor=self.doctor,
            start=end - timedelta(minutes=30),
            end=end,
        )
        return Appointment.objects.create(
            doctor_slot=slot,
            patient=self.user,
            price=self.doctor.price_per_visit,
            **kwargs,
        )

    def test_marks_past_booked_as_no_show(self, mock_send):
        past = self._make_past_appointment()

        with self.captureOnCommitCallbacks(execute=True):
            result = mark_no_shows()

        past.refresh_from_db()
        self.assertEqual(past.status, Appointment.Status.NO_SHOW)
        self.assertEqual(result, 1)
        self.mock_payment.delay.assert_called_once_with(past.pk, Payment.Type.NO_SHOW_FEE)
        mock_send.assert_called_once()

    def test_future_appointment_untouched(self, mock_send):
        mark_no_shows()

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.BOOKED)

    def test_only_booked_are_affected(self, mock_send):
        done = self._make_past_appointment(status=Appointment.Status.COMPLETED)

        mark_no_shows()

        done.refresh_from_db()
        self.assertEqual(done.status, Appointment.Status.COMPLETED)

    def test_sends_message_when_nothing_missed(self, mock_send):
        with self.captureOnCommitCallbacks(execute=True):
            result = mark_no_shows()

        self.assertEqual(result, 0)
        mock_send.assert_called_once_with("No missed appointments today!")

    @patch("appointments.tasks.mark_no_show", side_effect=[RuntimeError("stripe"), None])
    def test_continues_after_error(self, mock_mark, mock_send):
        self._make_past_appointment(hours_ago=1)
        self._make_past_appointment(hours_ago=3)

        with self.assertLogs("appointments.tasks", level="ERROR"):
            result = mark_no_shows()

        self.assertEqual(mock_mark.call_count, 2)
        self.assertEqual(result, 1)

    def test_skips_appointment_completed_after_listing(self, mock_send):
        # Simulates an admin completing a visit while the task is already running
        first = self._make_past_appointment(hours_ago=1)
        second = self._make_past_appointment(hours_ago=3)
        real_mark_no_show = services.mark_no_show
        completed = []

        def complete_other_then_mark(appointment, request=None):
            if not completed:
                other = second if appointment.pk == first.pk else first
                Appointment.objects.filter(pk=other.pk).update(
                    status=Appointment.Status.COMPLETED,
                    completed_at=timezone.now(),
                )
                completed.append(other.pk)
            return real_mark_no_show(appointment, request)

        with (
            self.captureOnCommitCallbacks(execute=True),
            patch("appointments.tasks.mark_no_show", side_effect=complete_other_then_mark) as mock_mark,
        ):
            result = mark_no_shows()

        self.assertEqual(result, 1)
        self.assertEqual(mock_mark.call_count, 1)
        self.mock_payment.delay.assert_called_once()
        other = Appointment.objects.get(pk=completed[0])
        self.assertEqual(other.status, Appointment.Status.COMPLETED)

    def test_skips_appointment_cancelled_after_listing(self, mock_send):
        first = self._make_past_appointment(hours_ago=1)
        second = self._make_past_appointment(hours_ago=3)
        real_mark_no_show = services.mark_no_show
        cancelled = []

        def cancel_other_then_mark(appointment, request=None):
            if not cancelled:
                other = second if appointment.pk == first.pk else first
                Appointment.objects.filter(pk=other.pk).update(status=Appointment.Status.CANCELLED)
                cancelled.append(other.pk)
            return real_mark_no_show(appointment, request)

        with (
            self.captureOnCommitCallbacks(execute=True),
            patch("appointments.tasks.mark_no_show", side_effect=cancel_other_then_mark),
        ):
            result = mark_no_shows()

        self.assertEqual(result, 1)
        self.mock_payment.delay.assert_called_once()
        other = Appointment.objects.get(pk=cancelled[0])
        self.assertEqual(other.status, Appointment.Status.CANCELLED)

    def test_logs_appointment_id_when_lock_query_fails(self, mock_send):
        past = self._make_past_appointment()

        with (
            patch.object(Appointment.objects, "select_for_update", side_effect=DatabaseError("locked")),
            self.assertLogs("appointments.tasks", level="ERROR") as logs,
        ):
            result = mark_no_shows()

        self.assertEqual(result, 0)
        self.assertIn(f"Failed to mark appointment {past.pk} as no-show", logs.output[0])
        self.mock_payment.delay.assert_not_called()
        past.refresh_from_db()
        self.assertEqual(past.status, Appointment.Status.BOOKED)
