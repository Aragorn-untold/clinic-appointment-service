from datetime import timedelta
from unittest.mock import MagicMock, patch

import stripe
from django.contrib.messages import get_messages
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from appointments.models import Appointment
from core.tests.base import BaseTestCase
from doctor_slots.models import DoctorSlot
from payments.models import Payment

CHANGELIST_URL = reverse("admin:appointments_appointment_changelist")


def change_url(appointment_id):
    return reverse("admin:appointments_appointment_change", args=[appointment_id])


def delete_url(appointment_id):
    return reverse("admin:appointments_appointment_delete", args=[appointment_id])


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class AppointmentAdminTests(BaseTestCase):
    """Status changes in the admin must go through services (payments, notifications),
    so the form is read-only and status is changed only by admin actions.

    Payments are created by a Celery task after commit: run_action executes it inline."""

    def setUp(self):
        super().setUp()
        self.web_client = Client()
        self.web_client.force_login(self.admin_user)

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

    def create_appointment(self, starts_in, **kwargs):
        start = timezone.now().replace(microsecond=0) + starts_in
        slot = DoctorSlot.objects.create(doctor=self.doctor, start=start, end=start + timedelta(minutes=30))
        return Appointment.objects.create(
            doctor_slot=slot,
            patient=self.user,
            price=self.doctor.price_per_visit,
            **kwargs,
        )

    def run_action(self, action, *appointments):
        with self.captureOnCommitCallbacks(execute=True):
            return self.web_client.post(
                CHANGELIST_URL,
                {"action": action, "_selected_action": [appointment.pk for appointment in appointments]},
            )

    def messages_of(self, response):
        return [(message.level_tag, str(message)) for message in get_messages(response.wsgi_request)]

    # read-only form, no add / delete

    def test_change_page_opens_without_editable_fields(self):
        res = self.web_client.get(change_url(self.appointment.pk))

        self.assertEqual(res.status_code, 200)
        form_fields = res.context["adminform"].form.fields
        for field in ("status", "price", "completed_at", "doctor_slot", "patient"):
            self.assertNotIn(field, form_fields)

    def test_status_cannot_be_changed_through_form(self):
        self.web_client.post(
            change_url(self.appointment.pk),
            {"status": Appointment.Status.COMPLETED, "price": "1.00"},
        )

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.BOOKED)
        self.assertEqual(self.appointment.price, self.doctor.price_per_visit)
        self.assertFalse(Payment.objects.filter(appointment=self.appointment).exists())

    def test_add_page_is_forbidden(self):
        res = self.web_client.get(reverse("admin:appointments_appointment_add"))

        self.assertEqual(res.status_code, 403)

    def test_delete_page_is_forbidden(self):
        res = self.web_client.get(delete_url(self.appointment.pk))

        self.assertEqual(res.status_code, 403)
        self.assertTrue(Appointment.objects.filter(pk=self.appointment.pk).exists())

    def test_bulk_delete_action_is_not_available(self):
        res = self.web_client.get(CHANGELIST_URL)

        action_names = [name for name, _ in res.context["action_form"].fields["action"].choices]
        self.assertNotIn("delete_selected", action_names)
        self.assertIn("complete_appointments", action_names)
        self.assertIn("cancel_appointments", action_names)
        self.assertIn("mark_no_show_appointments", action_names)

    # complete action (real service, Stripe mocked)

    def test_complete_action_completes_and_creates_payment(self):
        res = self.run_action("complete_appointments", self.appointment)

        self.assertEqual(res.status_code, 302)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.COMPLETED)
        self.assertIsNotNone(self.appointment.completed_at)
        payment = Payment.objects.get(appointment=self.appointment)
        self.assertEqual(payment.type, Payment.Type.CONSULTATION)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.mock_notify.assert_called_once()
        levels = [level for level, _ in self.messages_of(res)]
        self.assertEqual(levels, ["success"])

    def test_complete_action_on_wrong_status_changes_nothing(self):
        cancelled = self.create_appointment(timedelta(days=3), status=Appointment.Status.CANCELLED)

        res = self.run_action("complete_appointments", cancelled)

        cancelled.refresh_from_db()
        self.assertEqual(cancelled.status, Appointment.Status.CANCELLED)
        self.assertIsNone(cancelled.completed_at)
        self.assertFalse(Payment.objects.filter(appointment=cancelled).exists())
        self.mock_notify.assert_not_called()
        messages = self.messages_of(res)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0][0], "error")
        self.assertIn(str(cancelled.pk), messages[0][1])

    def test_complete_action_with_mixed_selection(self):
        cancelled = self.create_appointment(timedelta(days=3), status=Appointment.Status.CANCELLED)

        res = self.run_action("complete_appointments", self.appointment, cancelled)

        self.appointment.refresh_from_db()
        cancelled.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.COMPLETED)
        self.assertEqual(cancelled.status, Appointment.Status.CANCELLED)
        self.assertEqual(Payment.objects.filter(appointment=self.appointment).count(), 1)
        self.assertFalse(Payment.objects.filter(appointment=cancelled).exists())
        levels = sorted(level for level, _ in self.messages_of(res))
        self.assertEqual(levels, ["error", "success"])

    @patch("appointments.services.create_appointment_payment")
    def test_complete_action_works_while_stripe_is_down(self, payment_task):
        self.mock_stripe_create.side_effect = stripe.error.APIConnectionError("Stripe is down")

        res = self.run_action("complete_appointments", self.appointment)

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.COMPLETED)
        self.mock_stripe_create.assert_not_called()
        payment_task.delay.assert_called_once_with(self.appointment.pk, Payment.Type.CONSULTATION)
        levels = [level for level, _ in self.messages_of(res)]
        self.assertEqual(levels, ["success"])

    # cancel / no-show actions call the matching service

    @patch("appointments.services.cancel_appointment")
    def test_cancel_action_calls_service_for_each_selected(self, cancel_mock):
        other = self.create_appointment(timedelta(days=3))

        self.run_action("cancel_appointments", self.appointment, other)

        self.assertEqual(cancel_mock.call_count, 2)
        called_ids = {call.args[0].pk for call in cancel_mock.call_args_list}
        self.assertEqual(called_ids, {self.appointment.pk, other.pk})

    def test_cancel_action_cancels_appointment(self):
        appointment = self.create_appointment(timedelta(days=3))

        self.run_action("cancel_appointments", appointment)

        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CANCELLED)
        self.assertFalse(Payment.objects.filter(appointment=appointment).exists())
        self.mock_notify.assert_called_once()

    @patch("appointments.services.mark_no_show")
    def test_no_show_action_calls_service_for_each_selected(self, no_show_mock):
        missed = self.create_appointment(-timedelta(hours=2))

        self.run_action("mark_no_show_appointments", missed)

        no_show_mock.assert_called_once()
        self.assertEqual(no_show_mock.call_args.args[0].pk, missed.pk)

    def test_no_show_action_on_future_appointment_changes_nothing(self):
        res = self.run_action("mark_no_show_appointments", self.appointment)

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.BOOKED)
        self.assertFalse(Payment.objects.filter(appointment=self.appointment).exists())
        self.mock_notify.assert_not_called()
        messages = self.messages_of(res)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0][0], "error")
        self.assertIn("already ended", messages[0][1])

    def test_no_show_action_marks_past_appointment_and_creates_fee(self):
        missed = self.create_appointment(-timedelta(hours=2))

        self.run_action("mark_no_show_appointments", missed)

        missed.refresh_from_db()
        self.assertEqual(missed.status, Appointment.Status.NO_SHOW)
        payment = Payment.objects.get(appointment=missed)
        self.assertEqual(payment.type, Payment.Type.NO_SHOW_FEE)
