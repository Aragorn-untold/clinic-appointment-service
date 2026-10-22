from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from core.tests.base import BaseTestCase
from payments.models import Payment
from payments.services import PaymentService


# ---------- Calculation Tests ----------
class PaymentServiceCalculationTests(SimpleTestCase):
    def test_consultation_amount(self):
        """CONSULTATION: 1.0 * price."""
        price = Decimal("800.00")
        result = PaymentService.calculate_amount(price, Payment.Type.CONSULTATION)
        self.assertEqual(result, Decimal("800.00"))

    def test_cancellation_fee_amount(self):
        """CANCELLATION_FEE: 0.5 * price."""
        price = Decimal("800.00")
        result = PaymentService.calculate_amount(price, Payment.Type.CANCELLATION_FEE)
        self.assertEqual(result, Decimal("400.00"))

    def test_no_show_fee_amount(self):
        """NO_SHOW_FEE: 1.2 * price."""
        price = Decimal("800.00")
        result = PaymentService.calculate_amount(price, Payment.Type.NO_SHOW_FEE)
        self.assertEqual(result, Decimal("960.00"))

    def test_rounding_precision(self):
        price = Decimal("33.33")
        result = PaymentService.calculate_amount(price, Payment.Type.CANCELLATION_FEE)
        self.assertEqual(result, Decimal("16.67"))

    def test_accepts_str_and_int_types(self):
        self.assertEqual(
            PaymentService.calculate_amount("800.00", Payment.Type.CONSULTATION),
            Decimal("800.00"),
        )

    def test_negative_price_raises_error(self):
        with self.assertRaises(ValueError):
            PaymentService.calculate_amount(Decimal("-100.00"), Payment.Type.CONSULTATION)

    def test_to_stripe_cents(self):
        self.assertEqual(PaymentService.to_stripe_cents(Decimal("10.00")), 1000)
        self.assertEqual(PaymentService.to_stripe_cents(Decimal("0.99")), 99)


# ---------- Stripe API ----------
class PaymentServiceStripeTests(BaseTestCase):
    @patch("stripe.checkout.Session.create")
    def test_create_payment_success(self, mock_stripe_create):
        mock_stripe_create.return_value = MagicMock(
            id="sess_test_123",
            url="https://checkout.stripe.com/pay/sess_test_123",
        )

        payment = PaymentService.create_payment_for_appointment(
            appointment=self.appointment,
            payment_type=Payment.Type.CONSULTATION,
        )

        self.assertEqual(payment.session_id, "sess_test_123")
        self.assertEqual(payment.money_to_pay, self.appointment.price)
        mock_stripe_create.assert_called_once()

    @patch("stripe.checkout.Session.create")
    def test_returns_existing_payment_without_calling_stripe(self, mock_stripe_create):
        existing_payment = Payment.objects.create(
            appointment=self.appointment,
            type=Payment.Type.CONSULTATION,
            status=Payment.Status.PENDING,
            session_id="sess_existing",
            session_url="https://checkout.stripe.com/existing",
            money_to_pay=self.appointment.price,
        )

        payment = PaymentService.create_payment_for_appointment(
            appointment=self.appointment,
            payment_type=Payment.Type.CONSULTATION,
        )

        self.assertEqual(payment.id, existing_payment.id)
        mock_stripe_create.assert_not_called()
