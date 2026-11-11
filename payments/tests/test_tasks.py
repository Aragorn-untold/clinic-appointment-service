from unittest.mock import MagicMock, patch

from core.tests.base import BaseTestCase
from notifications.messages import payment_succeeded
from payments.models import Payment
from payments.services import PaymentService
from payments.tasks import expire_stale_payment_sessions


class ExpireStaleSessionsServiceTests(BaseTestCase):
    @patch("stripe.checkout.Session.retrieve")
    def test_marks_expired_session_as_expired(self, mock_retrieve):
        payment = Payment.objects.create(
            appointment=self.appointment,
            type=Payment.Type.CONSULTATION,
            status=Payment.Status.PENDING,
            session_id="sess_expired_111",
            session_url="https://checkout.stripe.com/expired_111",
            money_to_pay=self.appointment.price,
        )
        mock_retrieve.return_value = MagicMock(status="expired")

        count = PaymentService.expire_stale_sessions()

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.EXPIRED)
        self.assertEqual(count, 1)

    @patch("stripe.checkout.Session.retrieve")
    def test_ignores_open_session(self, mock_retrieve):
        payment = Payment.objects.create(
            appointment=self.appointment,
            type=Payment.Type.CONSULTATION,
            status=Payment.Status.PENDING,
            session_id="sess_open_222",
            session_url="https://checkout.stripe.com/open_222",
            money_to_pay=self.appointment.price,
        )
        mock_retrieve.return_value = MagicMock(status="open")

        count = PaymentService.expire_stale_sessions()

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(count, 0)

    @patch("stripe.checkout.Session.retrieve")
    def test_ignores_complete_session(self, mock_retrieve):
        payment = Payment.objects.create(
            appointment=self.appointment,
            type=Payment.Type.CONSULTATION,
            status=Payment.Status.PENDING,
            session_id="sess_complete_333",
            session_url="https://checkout.stripe.com/complete_333",
            money_to_pay=self.appointment.price,
        )
        mock_retrieve.return_value = MagicMock(status="complete")

        count = PaymentService.expire_stale_sessions()

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(count, 0)

    @patch("stripe.checkout.Session.retrieve")
    def test_skips_payment_on_stripe_error(self, mock_retrieve):
        import stripe as stripe_module

        payment = Payment.objects.create(
            appointment=self.appointment,
            type=Payment.Type.CONSULTATION,
            status=Payment.Status.PENDING,
            session_id="sess_error_444",
            session_url="https://checkout.stripe.com/error_444",
            money_to_pay=self.appointment.price,
        )
        mock_retrieve.side_effect = stripe_module.error.StripeError("network error")

        count = PaymentService.expire_stale_sessions()

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(count, 0)

    @patch("stripe.checkout.Session.retrieve")
    def test_does_not_touch_already_paid(self, mock_retrieve):
        Payment.objects.create(
            appointment=self.appointment,
            type=Payment.Type.CONSULTATION,
            status=Payment.Status.PAID,
            session_id="sess_paid_555",
            session_url="https://checkout.stripe.com/paid_555",
            money_to_pay=self.appointment.price,
        )
        mock_retrieve.return_value = MagicMock(status="expired")

        PaymentService.expire_stale_sessions()

        mock_retrieve.assert_not_called()


@patch("payments.services.notify_admins")
@patch("stripe.checkout.Session.retrieve")
class PaidSessionSyncTests(BaseTestCase):
    """Task 5.1 (5): a paid session stays PENDING if the patient closes the tab
    before the success page. The scheduled task marks it PAID."""

    def setUp(self):
        super().setUp()
        self.payment = Payment.objects.create(
            appointment=self.appointment,
            type=Payment.Type.CONSULTATION,
            status=Payment.Status.PENDING,
            session_id="sess_paid_666",
            session_url="https://checkout.stripe.com/paid_666",
            money_to_pay=self.appointment.price,
        )

    def test_marks_paid_session_as_paid(self, mock_retrieve, mock_notify):
        mock_retrieve.return_value = MagicMock(status="complete", payment_status="paid")

        count = PaymentService.expire_stale_sessions()

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PAID)
        self.assertEqual(count, 0)  # only EXPIRED payments are counted

    def test_notifies_admins_once_when_marked_paid(self, mock_retrieve, mock_notify):
        mock_retrieve.return_value = MagicMock(status="complete", payment_status="paid")

        PaymentService.expire_stale_sessions()
        PaymentService.expire_stale_sessions()

        self.payment.refresh_from_db()
        mock_notify.assert_called_once_with(payment_succeeded(self.payment))

    def test_complete_but_unpaid_session_stays_pending(self, mock_retrieve, mock_notify):
        mock_retrieve.return_value = MagicMock(status="complete", payment_status="unpaid")

        PaymentService.expire_stale_sessions()

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PENDING)
        mock_notify.assert_not_called()

    def test_no_second_notification_if_success_page_marked_it_first(self, mock_retrieve, mock_notify):
        def success_page_wins(session_id):
            # The success page marks the payment PAID while the task is running
            Payment.objects.filter(pk=self.payment.pk).update(status=Payment.Status.PAID)
            return MagicMock(status="complete", payment_status="paid")

        mock_retrieve.side_effect = success_page_wins

        PaymentService.expire_stale_sessions()

        mock_notify.assert_not_called()

    def test_handles_expired_and_paid_together(self, mock_retrieve, mock_notify):
        expired = Payment.objects.create(
            appointment=self.appointment,
            type=Payment.Type.NO_SHOW_FEE,
            status=Payment.Status.PENDING,
            session_id="sess_expired_777",
            session_url="https://checkout.stripe.com/expired_777",
            money_to_pay=self.appointment.price,
        )
        sessions = {
            "sess_paid_666": MagicMock(status="complete", payment_status="paid"),
            "sess_expired_777": MagicMock(status="expired", payment_status="unpaid"),
        }
        mock_retrieve.side_effect = lambda session_id: sessions[session_id]

        count = PaymentService.expire_stale_sessions()

        self.payment.refresh_from_db()
        expired.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PAID)
        self.assertEqual(expired.status, Payment.Status.EXPIRED)
        self.assertEqual(count, 1)


class ExpireStaleSessionsTaskTests(BaseTestCase):
    @patch("payments.services.PaymentService.expire_stale_sessions")
    def test_task_delegates_to_service(self, mock_service):
        mock_service.return_value = 3

        result = expire_stale_payment_sessions()

        mock_service.assert_called_once()
        self.assertEqual(result, 3)


@patch("payments.services.notify_admins")
@patch("stripe.checkout.Session.retrieve")
class ExpireStaleSessionsRaceTests(BaseTestCase):
    """The sync task must not overwrite a payment that changed while it was asking Stripe."""

    def make_payment(self, session_id, payment_type=Payment.Type.CONSULTATION):
        return Payment.objects.create(
            appointment=self.appointment,
            type=payment_type,
            status=Payment.Status.PENDING,
            session_id=session_id,
            session_url=f"https://checkout.stripe.com/{session_id}",
            money_to_pay=self.appointment.price,
        )

    def test_does_not_expire_payment_paid_during_sync(self, mock_retrieve, mock_notify):
        payment = self.make_payment("sess_race_paid")

        def success_page_marks_paid(session_id):
            # The patient paid and the success page ran while the task was waiting for Stripe
            Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.PAID)
            return MagicMock(status="expired", payment_status="unpaid")

        mock_retrieve.side_effect = success_page_marks_paid

        count = PaymentService.expire_stale_sessions()

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(count, 0)

    def test_does_not_expire_renewed_payment(self, mock_retrieve, mock_notify):
        payment = self.make_payment("sess_race_old")

        def patient_renews(session_id):
            # The payment was renewed meanwhile: PENDING again, with a new session
            Payment.objects.filter(pk=payment.pk).update(
                session_id="sess_race_new",
                session_url="https://checkout.stripe.com/sess_race_new",
                status=Payment.Status.PENDING,
            )
            return MagicMock(status="expired", payment_status="unpaid")

        mock_retrieve.side_effect = patient_renews

        count = PaymentService.expire_stale_sessions()

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.session_id, "sess_race_new")
        self.assertEqual(count, 0)
        mock_retrieve.assert_called_once_with("sess_race_old")

    def test_expired_count_ignores_skipped_payments(self, mock_retrieve, mock_notify):
        changed = self.make_payment("sess_count_changed")
        untouched = self.make_payment("sess_count_untouched", payment_type=Payment.Type.NO_SHOW_FEE)

        def retrieve(session_id):
            if session_id == "sess_count_changed":
                Payment.objects.filter(pk=changed.pk).update(status=Payment.Status.PAID)
            return MagicMock(status="expired", payment_status="unpaid")

        mock_retrieve.side_effect = retrieve

        count = PaymentService.expire_stale_sessions()

        changed.refresh_from_db()
        untouched.refresh_from_db()
        self.assertEqual(changed.status, Payment.Status.PAID)
        self.assertEqual(untouched.status, Payment.Status.EXPIRED)
        self.assertEqual(count, 1)

    def test_each_payment_is_updated_right_after_its_stripe_check(self, mock_retrieve, mock_notify):
        # The first payment is already EXPIRED when Stripe is asked about the second one
        first = self.make_payment("sess_order_1")
        second = self.make_payment("sess_order_2", payment_type=Payment.Type.NO_SHOW_FEE)
        statuses_seen = {}

        def retrieve(session_id):
            other = second if session_id == "sess_order_1" else first
            statuses_seen[session_id] = Payment.objects.get(pk=other.pk).status
            return MagicMock(status="expired", payment_status="unpaid")

        mock_retrieve.side_effect = retrieve

        PaymentService.expire_stale_sessions()

        # Whichever payment is checked second must see the first one already EXPIRED
        self.assertIn(Payment.Status.EXPIRED, statuses_seen.values())
        self.assertIn(Payment.Status.PENDING, statuses_seen.values())
