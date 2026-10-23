from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone

from appointments.models import Appointment
from appointments.tasks import mark_no_shows
from core.tests.base import BaseTestCase
from doctor_slots.models import DoctorSlot


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
@patch("notifications.tasks.send_telegram_message")
class MarkNoShowsTaskTests(BaseTestCase):
    def _make_past_appointment(self, **kwargs):
        end = timezone.now() - timedelta(hours=1)
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

        result = mark_no_shows()

        past.refresh_from_db()
        self.assertEqual(past.status, Appointment.Status.NO_SHOW)
        self.assertEqual(result, 1)
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
        result = mark_no_shows()

        self.assertEqual(result, 0)
        mock_send.assert_called_once_with("No missed appointments today!")
