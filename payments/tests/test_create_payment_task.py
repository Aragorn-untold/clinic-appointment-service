from unittest.mock import MagicMock, patch

import stripe
from celery.exceptions import Retry

from appointments.models import Appointment
from core.tests.base import BaseTestCase
from payments.models import Payment
from payments.tasks import create_appointment_payment

# shared_task returns a proxy: patch attributes on the real task object
TASK = create_appointment_payment._get_current_object()


@patch("payments.tasks.notify_admins")
@patch("payments.services.stripe.checkout.Session.create")
class CreateAppointmentPaymentTaskTests(BaseTestCase):
    """The task that creates the Stripe payment after a status change (appointments.services)."""

    def run_task(self, payment_type="CONSULTATION", appointment_id=None, retries=0, throw=True, task_id=None):
        # Celery passes arguments as JSON, so payment_type arrives as a plain string
        return TASK.apply(
            args=(appointment_id or self.appointment.pk, payment_type),
            retries=retries,
            throw=throw,
            task_id=task_id,
        )

    def stripe_ok(self, mock_create):
        mock_create.return_value = MagicMock(id="cs_test_1", url="https://checkout.stripe.com/c/pay/cs_test_1")

    def test_creates_pending_payment(self, mock_create, mock_notify):
        self.stripe_ok(mock_create)

        self.run_task()

        payment = Payment.objects.get(appointment=self.appointment)
        self.assertEqual(payment.type, Payment.Type.CONSULTATION)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.session_id, "cs_test_1")
        self.assertEqual(payment.money_to_pay, self.appointment.price)
        mock_notify.assert_not_called()

    def test_passes_task_id_as_idempotency_key(self, mock_create, mock_notify):
        # Retries keep the same task id, so Stripe returns the same session instead of a new one
        self.stripe_ok(mock_create)

        self.run_task(task_id="task-abc-123")

        self.assertEqual(mock_create.call_args.kwargs["idempotency_key"], "payment-task-task-abc-123")

    def test_retry_uses_same_idempotency_key(self, mock_create, mock_notify):
        mock_create.side_effect = [
            stripe.error.APIConnectionError("Stripe is down"),
            MagicMock(id="cs_test_1", url="https://checkout.stripe.com/c/pay/cs_test_1"),
        ]

        with patch.object(TASK, "retry", side_effect=Retry()):
            self.run_task(task_id="task-abc-123", throw=False)
        self.run_task(task_id="task-abc-123", retries=1)

        keys = [call.kwargs["idempotency_key"] for call in mock_create.call_args_list]
        self.assertEqual(keys, ["payment-task-task-abc-123", "payment-task-task-abc-123"])
        self.assertEqual(Payment.objects.filter(appointment=self.appointment).count(), 1)

    def test_does_nothing_if_payment_already_exists(self, mock_create, mock_notify):
        # e.g. Celery ran the task twice
        Payment.objects.create(
            appointment=self.appointment,
            type=Payment.Type.CONSULTATION,
            status=Payment.Status.PENDING,
            session_id="cs_existing",
            session_url="https://checkout.stripe.com/existing",
            money_to_pay=self.appointment.price,
        )

        self.run_task()

        mock_create.assert_not_called()
        self.assertEqual(Payment.objects.filter(appointment=self.appointment).count(), 1)

    def test_retries_on_stripe_error(self, mock_create, mock_notify):
        mock_create.side_effect = stripe.error.APIConnectionError("Stripe is down")

        with patch.object(TASK, "retry", side_effect=Retry()) as retry_mock:
            self.run_task(throw=False)

        retry_mock.assert_called_once()
        self.assertEqual(retry_mock.call_args.kwargs["countdown"], 30)
        self.assertIsInstance(retry_mock.call_args.kwargs["exc"], RuntimeError)
        self.assertFalse(Payment.objects.filter(appointment=self.appointment).exists())
        mock_notify.assert_not_called()

    def test_retry_delay_grows(self, mock_create, mock_notify):
        mock_create.side_effect = stripe.error.APIConnectionError("Stripe is down")

        with patch.object(TASK, "retry", side_effect=Retry()) as retry_mock:
            self.run_task(retries=2, throw=False)

        self.assertEqual(retry_mock.call_args.kwargs["countdown"], 120)

    def test_gives_up_and_notifies_admins_after_last_retry(self, mock_create, mock_notify):
        mock_create.side_effect = stripe.error.APIConnectionError("Stripe is down")

        with (
            patch.object(TASK, "retry") as retry_mock,
            self.assertLogs("payments.tasks", level="ERROR") as logs,
            self.assertRaises(RuntimeError),
        ):
            self.run_task(retries=TASK.max_retries)

        retry_mock.assert_not_called()
        mock_notify.assert_called_once()
        message = mock_notify.call_args.args[0]
        self.assertIn(f"#{self.appointment.pk}", message)
        self.assertIn("CONSULTATION", message)
        self.assertIn(str(self.appointment.pk), logs.output[0])
        self.assertFalse(Payment.objects.filter(appointment=self.appointment).exists())

    def test_no_retry_for_missing_appointment(self, mock_create, mock_notify):
        with patch.object(TASK, "retry") as retry_mock, self.assertRaises(Appointment.DoesNotExist):
            self.run_task(appointment_id=999_999)

        retry_mock.assert_not_called()
        mock_create.assert_not_called()
